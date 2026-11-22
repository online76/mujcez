# Můj ČEZ pro Home Assistant

Neoficiální integrace portálu [Můj ČEZ](https://muj.cez.cz) (ČEZ Prodej). Načte všechna odběrná místa
elektřiny a plynu na účtu a ke každému vytvoří zařízení se senzory. Součástí je karta
`custom:mujcez-card` s výběrem odběrného místa.

## Co integrace zobrazuje

Pro každé odběrné místo (EAN / EIC):

| Senzor | Obsah |
|---|---|
| K úhradě | nezaplacené doklady (Kč), splatnost, seznam dokladů |
| Záloha | výše zálohy, frekvence, příští splatnost, zda jde měnit, způsob platby |
| Příští záloha | datum další splatnosti |
| Stav měřidla (+ NT) | poslední odečet elektroměru (kWh, VT/NT) nebo plynoměru (m³), historie odečtů |
| Poslední odečet | datum |
| Spotřeba / náklad za poslední období | kWh a Kč (u měsíční fakturace poslední měsíc, jinak poslední roční období) |
| Roční spotřeba | kWh a Kč, historie let |
| Poslední vyúčtování | částka, datum, splatnost, období, stav |
| Produkt | produkt, platnost, text smlouvy, distributor, sazba, jistič |
| Přehled | všechna data místa v atributech (pro kartu) |

Data se stahují každé 3 hodiny, přihlášení se udržuje každých 10 minut.

## Instalace

HACS → Vlastní repozitáře → `https://github.com/online76/mujcez` (Integrace), nebo zkopírovat
`custom_components/mujcez` do `/config/custom_components/` a restartovat HA.

## Přihlášení (bez zadávání hesla do HA)

1. Nastavení → Zařízení a služby → Přidat integraci → **Můj ČEZ**.
2. Klikni na odkaz pro přihlášení a přihlas se do Můj ČEZ jako obvykle.
3. Prohlížeč skončí na adrese `https://muj.cez.cz/col/auth-callback?code=…` (stránka může zůstat prázdná).
   Zkopíruj celou adresu z adresního řádku a vlož ji do Home Assistantu.

Integrace použije jednorázový kód (OAuth2 + PKCE, stejně jako webový portál) a dál si přihlášení
obnovuje sama. Když přihlášení vyprší, HA nabídne znovu přihlásit stejným způsobem.

## Karta

Karta se načte automaticky (není potřeba přidávat zdroj).

```yaml
type: custom:mujcez-card
komodita: elektrina   # nebo plyn
vychozi: Veselí 125   # výchozí odběrné místo (začátek názvu); vybrané místo si karta pamatuje
```

Obsahuje výběr odběrného místa, k úhradě, zálohu, stav měřidla, spotřebu za poslední období a rok,
poslední vyúčtování, graf spotřeby (u elektřiny VT/NT), doklady, odečty a údaje o smlouvě a místě.

## Testy

```bash
python -m pytest tests
```

*Integrace není produktem ČEZ. Používá stejné rozhraní jako webový portál, které se může bez upozornění změnit.*
