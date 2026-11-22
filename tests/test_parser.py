"""Test převodu dat (python -m pytest tests) – zkrácené skutečné odpovědi portálu."""

from datetime import date
import importlib.util
import pathlib

_p = pathlib.Path(__file__).parents[1] / "custom_components" / "mujcez" / "parser.py"
_s = importlib.util.spec_from_file_location("parser", _p)
parser = importlib.util.module_from_spec(_s)
_s.loader.exec_module(parser)

CB = "cz.cez.cpr.restapi.common.v1_0.dto.CodebookEntryDto"


def c(v):
    return {"@class": CB, "value": v}


GAS = {
    "point": {
        "consumptionPlaceIdIsu": "1000506972",
        "agreement": {"agreementIdIsu": "000070123114"},
        "supplyPointCode": "27ZG500Z00094533",
        "contract": {"contractAdvancePaymentAmount": 3800.0, "contractAdvancePaymentFrequency": c("01"),
                     "contractName": "Veselí 125 plyn - 29.07.2029"},
        "consumptionPlaceName": "Veselí 125 plyn - 29.07.2029",
        "canChangeAdvancePayments": True,
        "supplyPointCommodity": c("P1"),
        "supplyPointUniqueId": "000070123114100050697227ZG500Z00094533",
        "hasMonthlyInvoicing": False,
    },
    "detail": {
        "Address": {"addressZipCode": "535 01", "addressCity": c("Přelouč"), "addressStreet": c("Veselí"),
                    "addressLandRegistryNumber": "125", "addressHouseNumber": ""},
        "Product": {"productInstanceValidityEndDate": "2029-07-29", "productInstanceValidityStartDate": "2026-07-29",
                    "productInstanceName": "Plyn Bez starostí na 3 roky"},
        "GassSupplyPoint": {"@class": "x.GassSupplyPointDto", "supplyPointCode": "27ZG500Z00094533",
                            "supplyPointNumber": "2277714", "supplyPointDistributor": c("GasNet, s.r.o."),
                            "gasSupplyPointIsHeatingFlag": True, "gasSupplyPointIsCookingFlag": True,
                            "supplyPointMeasurementKind": c("Plyn - C")},
        "hasMonthlyInvoicing": False,
    },
    "year": [
        {"dateTo": "2025-10-06", "dateFrom": "2024-10-08", "consumptionHT": 17030.21, "consumptionLT": 0E-14,
         "consumptionSum": 17030.21, "consumptionAmount": 46658.46, "product": "Roční fakturace"},
        {"dateTo": "2026-10-01", "dateFrom": "2025-10-07", "consumptionHT": 13589.28, "consumptionLT": 0E-14,
         "consumptionSum": 13589.28, "consumptionAmount": 35298.61, "product": "Roční fakturace"},
    ],
    "month": [
        {"dateTo": "2026-10-01", "dateFrom": "2025-10-07", "consumptionSum": 13589.28, "product": "Roční fakturace"},
    ],
    "readings": [
        {"meterReadingTariff": {"@class": CB, "entryId": "1205.0"}, "deviceSerialNumber": "2277714",
         "meterReadingValueHT": 38965, "meterReadingValueLT": 0, "meterReadingRequestRegisterDate": "2026-10-01",
         "selfMeterReadingMethodId": "ZN", "meterReadingDoubleTariffFlag": False},
        {"meterReadingTariff": {"@class": CB, "entryId": "1521.0"}, "deviceSerialNumber": "2277714",
         "meterReadingValueHT": 37760, "meterReadingValueLT": 0, "meterReadingRequestRegisterDate": "2025-10-06",
         "selfMeterReadingMethodId": "ZN", "meterReadingDoubleTariffFlag": False},
    ],
    "advance": {"advancePaymentPlanCurrentAmount": 3800.0,
                "firstFollowingPaymentPrescription": {"paymentPrescriptionDueDate": "2026-12-14"}},
}

ELE = {
    "point": {"agreement": {"agreementIdIsu": "000044086392"}, "supplyPointCode": "859182400707048034",
              "consumptionPlaceName": "Veselí 125", "supplyPointCommodity": c("E1"),
              "contract": {"contractAdvancePaymentAmount": 0.0, "contractAdvancePaymentFrequency": c("00")},
              "supplyPointUniqueId": "u2", "hasMonthlyInvoicing": True,
              "advancePaymentChangeNotPossibleReason": c("Aktuálně nelze měnit zálohy.")},
    "detail": {"ElectricitySupplyPoint": {"doubleTariff": True, "electricitySupplyPointDistributionRate": c("D45D - Přímotop"),
                                          "electricitySupplyPointReservedPowerPerBreaker": 50,
                                          "electricitySupplyPointNumberOfPhases": 3},
               "Product": {"productInstanceName": "Elektřina SPOT", "productInstanceValidityEndDate": "9999-12-31"},
               "hasMonthlyInvoicing": True, "productType": "SPOT"},
    "year": [],
    "month": [
        {"dateTo": "2026-09-30", "dateFrom": "2026-09-01", "consumptionHT": 7, "consumptionLT": 38, "consumptionSum": 45,
         "consumptionAmount": 1699.31, "product": "Měsíční fakturace"},
        {"dateTo": "2026-10-31", "dateFrom": "2026-10-01", "consumptionHT": 5, "consumptionLT": 184, "consumptionSum": 189,
         "consumptionAmount": 2612.27, "product": "Měsíční fakturace"},
    ],
    "readings": [],
    "advance": {},
}

BILLINGS = [
    {"billingAccountingDocumentTypeText": "Vyúčtování", "billingAccountingDocumentType": "VYU",
     "billingMaturityDate": "2026-11-25", "billingTotalAmount": 2612.27, "billingAccountingDocumentNumber": "2643459104",
     "billingSettlementPeriodTo": "2026-10-31", "billingSettlementPeriodFrom": "2026-10-01",
     "billingAccountingDocumentDate": "2026-11-11", "agreementIdIsu": "000044086392", "isPaid": False,
     "balance": 2612.27, "shouldBePaid": True, "statusText": "UNPAID"},
    {"billingAccountingDocumentTypeText": "Záloha", "billingAccountingDocumentType": "ZAL",
     "billingTotalAmount": 3800, "billingAccountingDocumentDate": "2026-11-14", "agreementIdIsu": "000070123114",
     "isPaid": True, "balance": 0, "shouldBePaid": False, "statusText": "PAID", "billingAccountingDocumentNumber": "9"},
]


def test_parse():
    out = parser.parse({"points": [GAS, ELE], "billings": BILLINGS}, date(2026, 11, 22))
    gas = out["27ZG500Z00094533"]
    assert gas["komodita"] == "plyn"
    assert gas["adresa"] == "Veselí 125, 535 01 Přelouč"
    assert gas["posledni_odecet"]["vt"] == 38965 and gas["posledni_odecet"]["datum"] == "2026-10-01"
    assert gas["jednotka_meridla"] == "m³"
    assert gas["zaloha"] == 3800 and gas["zaloha_pristi"] == "2026-12-14" and gas["zaloha_frekvence"] == "měsíčně"
    assert gas["spotreba_mesice"] == [] and gas["posledni_obdobi"]["kwh"] == 13589.28
    assert gas["vyuziti"] == "vytápění, vaření" and gas["distributor"] == "GasNet, s.r.o."
    assert gas["k_uhrade"] == 0 and gas["doklady"][0]["typ"] == "Záloha"
    ele = out["859182400707048034"]
    assert ele["komodita"] == "elektrina" and ele["sazba"] == "D45D - Přímotop" and ele["dvoutarif"]
    assert ele["k_uhrade"] == 2612.27 and ele["k_uhrade_splatnost"] == "2026-11-25"
    assert ele["posledni_vyuctovani"]["castka"] == 2612.27
    assert ele["posledni_obdobi"]["kwh"] == 189 and ele["posledni_obdobi"]["nt"] == 184
    assert ele["produkt_do"] is None and ele["zaloha_frekvence"] == "bez záloh"
    assert ele["zaloha_proc_nelze"] == "Aktuálně nelze měnit zálohy."
