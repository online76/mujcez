"""Převod odpovědí portálu Můj ČEZ na přehledná data odběrných míst (bez závislosti na HA)."""

from __future__ import annotations

from datetime import date
from typing import Any

COMMODITY = {"E1": "elektrina", "P1": "plyn"}

FREQ = {"00": "bez záloh", "01": "měsíčně", "02": "čtvrtletně", "03": "pololetně", "04": "ročně"}

READ_METHOD = {
    "ZN": "odečet distributora",
    "ZO": "samoodečet",
    "ZP": "odhad",
    "ZS": "samoodečet",
}

STATUS = {"PAID": "zaplaceno", "UNPAID": "nezaplaceno", "PARTIALLY_PAID": "částečně zaplaceno",
          "OVERDUE": "po splatnosti", "OVERPAYMENT": "přeplatek"}

ADVANCE_KINDS = ("BBP", "ZAL")


def cb(value: Any) -> Any:
    """Číselníková položka portálu {"@class": ...CodebookEntryDto, "value": ...} -> text."""
    if isinstance(value, dict) and "CodebookEntryDto" in str(value.get("@class", "")):
        return value.get("value") or value.get("entryId") or value.get("entrySystemSpecificId") or ""
    return value


def num(value: Any) -> float | None:
    try:
        return round(float(value), 2)
    except (TypeError, ValueError):
        return None


def _addr(a: dict[str, Any]) -> str:
    if not a:
        return ""
    street = cb(a.get("addressStreet")) or ""
    no = a.get("addressLandRegistryNumber") or ""
    if a.get("addressHouseNumber"):
        no = f"{no}/{a['addressHouseNumber']}"
    city = cb(a.get("addressCity")) or ""
    zipc = a.get("addressZipCode") or ""
    return ", ".join(x for x in (f"{street} {no}".strip(), f"{zipc} {city}".strip()) if x)


def _period(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for r in rows or []:
        out.append(
            {
                "od": r.get("dateFrom"),
                "do": r.get("dateTo"),
                "kwh": num(r.get("consumptionSum")),
                "vt": num(r.get("consumptionHT")),
                "nt": num(r.get("consumptionLT")),
                "kc": num(r.get("consumptionAmount")),
                "zpusob": r.get("product") or "",
            }
        )
    out.sort(key=lambda x: x["od"] or "")
    return out


def _readings(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for r in rows or []:
        d = r.get("meterReadingRequestRegisterDate")
        if not d:
            continue
        out.append(
            {
                "datum": d,
                "vt": num(r.get("meterReadingValueHT")),
                "nt": num(r.get("meterReadingValueLT")) if r.get("meterReadingDoubleTariffFlag") else None,
                "spotreba": num(cb(r.get("meterReadingTariff"))),
                "meridlo": r.get("deviceSerialNumber") or "",
                "zpusob": READ_METHOD.get(r.get("selfMeterReadingMethodId") or "", r.get("selfMeterReadingMethodId") or ""),
            }
        )
    out.sort(key=lambda x: x["datum"])
    # spotřeba mezi odečty (portál u elektřiny uvádí jen VT, proto se počítá z rozdílu stavů)
    prev = None
    for r in out:
        total = (r["vt"] or 0) + (r["nt"] or 0)
        r["spotreba"] = round(total - prev, 2) if prev is not None and total >= prev else None
        prev = total
    return out


def _sum_months(months: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Součet posledních 12 měsíců (u měsíční fakturace)."""
    last = months[-12:]
    if not last:
        return None
    s = lambda k: round(sum(m[k] or 0 for m in last), 2)  # noqa: E731
    return {"od": last[0]["od"], "do": last[-1]["do"], "kwh": s("kwh"), "vt": s("vt"), "nt": s("nt"),
            "kc": s("kc"), "zpusob": "posledních 12 měsíců"}


def _billing(b: dict[str, Any]) -> dict[str, Any]:
    status = b.get("statusText") or ""
    total = num(b.get("billingTotalAmount"))
    rest = num(b.get("balance", b.get("billingBalance")))
    if not total:
        # předpis zálohy (BBP) má částku jen ve zbývající části, platba (PLB) v uhrazené částce
        total = rest or num(abs(b.get("billingEColClearingAmount") or 0)) or num(abs(b.get("billingEColPaidAmount") or 0)) or total
    if total is not None and total < 0:
        status = "OVERPAYMENT"
    return {
        "typ": b.get("billingAccountingDocumentTypeText") or b.get("billingAccountingDocumentType") or "",
        "kod": b.get("billingAccountingDocumentType") or "",
        "cislo": b.get("billingAccountingDocumentNumber") or "",
        "datum": b.get("billingAccountingDocumentDate") or b.get("billingAccountingDocumentAcquisitionDate"),
        "splatnost": b.get("billingMaturityDate"),
        "castka": total,
        "zbyva": rest,
        "zaplaceno": bool(b.get("isPaid")),
        "uhradit": bool(b.get("shouldBePaid")),
        "preplatek": bool(b.get("isOverpayment") or b.get("billingIsNegative")),
        "po_splatnosti_dnu": b.get("daysPastDue") or 0,
        "stav": STATUS.get(status, status.lower()),
        "obdobi_od": b.get("billingSettlementPeriodFrom"),
        "obdobi_do": b.get("billingSettlementPeriodTo"),
        "vs": b.get("billingVariableSymbol") or "",
    }


def parse(raw: dict[str, Any], today: date | None = None) -> dict[str, dict[str, Any]]:
    """Vrátí {kód EAN/EIC: data odběrného místa}."""
    today = today or date.today()
    by_agreement: dict[str, list[dict[str, Any]]] = {}
    for b in raw.get("billings") or []:
        by_agreement.setdefault(b.get("agreementIdIsu") or "", []).append(_billing(b))

    out: dict[str, dict[str, Any]] = {}
    for item in raw.get("points") or []:
        sp = item.get("point") or {}
        det = item.get("detail") or {}
        adv = item.get("advance") or {}
        commodity_code = cb(sp.get("supplyPointCommodity")) or ""
        tech = det.get("ElectricitySupplyPoint") or det.get("GassSupplyPoint") or det.get("GasSupplyPoint") or {}
        product = det.get("Product") or {}
        pay = (det.get("PaymentSettings") or {}).get("actualAdvancePaymentMethod") or {}
        agreement = (sp.get("agreement") or {}).get("agreementIdIsu") or (det.get("SupplyPointDetailAgreement") or {}).get("agreementIdIsu") or ""
        contract = sp.get("contract") or {}
        code = sp.get("supplyPointCode") or tech.get("supplyPointCode") or ""
        is_gas = commodity_code == "P1"

        today_s = today.isoformat()
        all_b = by_agreement.get(agreement, [])
        # budoucí předpisy záloh (splatnost až v budoucnu) nejsou dluh – jdou do samostatného plánu
        planned = sorted(
            (b for b in all_b if b["kod"] in ADVANCE_KINDS and not b["zaplaceno"] and (b["splatnost"] or "") > today_s),
            key=lambda x: x["splatnost"] or "",
        )
        billings = sorted(
            (b for b in all_b if b not in planned),
            key=lambda x: (x["datum"] or "", x["splatnost"] or "", x["cislo"]),
            reverse=True,
        )
        unpaid = [b for b in billings if b["uhradit"] and not b["zaplaceno"] and (b["zbyva"] or 0) > 0]
        invoices = [b for b in billings if b["kod"] in ("VYU", "FA", "INV") or b["typ"].lower().startswith("vyúčt")]
        readings = _readings(item.get("readings"))
        year = _period(item.get("year"))
        monthly = bool(det.get("hasMonthlyInvoicing") or sp.get("hasMonthlyInvoicing"))
        # u ročně fakturovaných míst vrací portál i pro "month" roční období – měsíce mají smysl jen u měsíční fakturace
        month = _period(item.get("month")) if monthly else []
        last_read = readings[-1] if readings else None

        next_due = (adv.get("firstFollowingPaymentPrescription") or {}).get("paymentPrescriptionDueDate")
        uses = []
        for key, label in (("gasSupplyPointIsHeatingFlag", "vytápění"), ("gasSupplyPointIsWaterHeatingFlag", "ohřev vody"),
                           ("gasSupplyPointIsCookingFlag", "vaření"), ("gasSupplyPointIsTechnicalFlag", "technologie")):
            if tech.get(key):
                uses.append(label)

        out[code] = {
            "kod": code,
            "komodita": COMMODITY.get(commodity_code, commodity_code.lower()),
            "nazev": sp.get("consumptionPlaceName") or contract.get("contractName") or code,
            "adresa": _addr(det.get("Address") or sp.get("address") or {}),
            "uid": sp.get("supplyPointUniqueId"),
            "smlouva": agreement,
            "produkt": product.get("productInstanceName") or sp.get("Product") or "",
            "produkt_typ": det.get("productType") or "",
            "produkt_od": product.get("productInstanceValidityStartDate"),
            "produkt_do": None if (product.get("productInstanceValidityEndDate") or "").startswith("9999") else product.get("productInstanceValidityEndDate"),
            "smlouva_text": product.get("productContractText") or "",
            "distributor": cb(tech.get("supplyPointDistributor")) or "",
            "sazba": cb(tech.get("electricitySupplyPointDistributionRate")) or "",
            "jistic_a": tech.get("electricitySupplyPointReservedPowerPerBreaker"),
            "faze": tech.get("electricitySupplyPointNumberOfPhases"),
            "napeti": cb(tech.get("voltageLevel")) or "",
            "dvoutarif": bool(tech.get("doubleTariff")),
            "hdo": bool(tech.get("electricitySupplyPointHasMassRemoteControl")),
            "mereni": cb(tech.get("supplyPointMeasurementKind")) or "",
            "typ_mereni": cb(tech.get("supplyPointMeasurementType")) or "",
            "prubehove_mereni": bool(tech.get("supplyPointIsContinuousMeasurement") or sp.get("supplyPointIsContinuousMeasurement")),
            "odecet": cb(tech.get("supplyPointReadWeek")) or "",
            "typ_mista": cb(tech.get("supplyPointType")) or cb(sp.get("supplyPointType")) or "",
            "kategorie": cb(tech.get("supplyPointCategory")) or "",
            "vyuziti": ", ".join(uses),
            "meridlo": tech.get("supplyPointNumber") or (last_read or {}).get("meridlo") or "",
            "jednotka_meridla": "m³" if is_gas else "kWh",
            "mesicni_fakturace": monthly,
            "platba_zaloh": pay.get("paymentMethodName") or "",
            "zaloha": num(adv.get("advancePaymentPlanCurrentAmount", contract.get("contractAdvancePaymentAmount"))),
            "zaloha_frekvence": FREQ.get(cb(contract.get("contractAdvancePaymentFrequency")) or "", ""),
            "zaloha_pristi": next_due,
            "zaloha_posledni": (adv.get("lastFollowingPaymentPrescription") or {}).get("paymentPrescriptionDueDate"),
            "zaloha_zbyva_plateb": adv.get("advancePaymentChangeRemainingPayments"),
            "zaloha_lze_zmenit": bool(sp.get("canChangeAdvancePayments")),
            "zaloha_proc_nelze": cb(sp.get("advancePaymentChangeNotPossibleReason")) or "",
            "k_uhrade": round(sum(b["zbyva"] or 0 for b in unpaid), 2),
            "k_uhrade_splatnost": min((b["splatnost"] for b in unpaid if b["splatnost"]), default=None),
            "nezaplacene": unpaid,
            "posledni_vyuctovani": invoices[0] if invoices else None,
            "doklady": billings[:24],
            "zalohy_plan": planned[:12],
            "odecty": readings[-12:],
            "posledni_odecet": last_read,
            "spotreba_roky": year,
            "spotreba_mesice": month[-24:],
            "posledni_obdobi": month[-1] if month else (year[-1] if year else None),
            "posledni_rok": _sum_months(month) if month else (year[-1] if year else None),
        }
    return out
