# Innebandy Play för Home Assistant

Följ ett lag från [play.innebandy.se](https://play.innebandy.se) i Home Assistant: kommande matcher, live-ställning med händelselogg, tabellplats, senaste resultat, målskyttar och trupp.

> **Status: alpha (0.3.0a1).** Integrationen använder solidsports webbtjänst, som inte är ett officiellt publikt API. Den kan ändras eller sluta fungera utan förvarning.
>
> Integrationen är inte framtagen av eller godkänd av Svenska Innebandyförbundet, Stockholms IBF eller någon förening.

## Funktioner

- **Nästa match:** titel, starttid, plats och de sex nästa matcherna som attribut.
- **Pågående match:** ställning, status (ej startad, pågår, paus, slut), period, målvakter och en händelselogg med mål och utvisningar.
- **Matchstatistik under match:** hämtas var 30:e sekund från 10 minuter före start till 15 minuter efter beräknat slut.
- **Match pågår:** binär sensor som är på under matchen.
- **Tabellplats:** placering, poäng, V/O/F, målskillnad och hela tabellen.
- **Resultat:** senaste matcherna med resultat, form (V/O/F) och bokföring för de senaste 10.
- **Målskyttar:** mål, assist och poäng för laget under säsongen.
- **Trupp:** spelare med nummer och ledare med roll.
- **Tjänsten `innebandy_play.refresh`:** hämtar matchlistan på nytt direkt.

Matchlistan och repriserna hämtas första gången när integrationen läggs till, och därefter lördag och söndag kl. 08. Tabellen uppdateras var 15:e minut och truppen var sjätte timme. Matchstatistik hämtas bara under matchfönstret.

## Installation

### Via HACS (rekommenderas)

1. Öppna HACS, klicka på ⋮ uppe till höger och välj **Anpassade förvaringsplatser**.
2. Klistra in `https://github.com/DITT-GITHUB-NAMN/ha-innebandy-play`, välj kategorin **Integration** och lägg till.
3. Sök efter **Innebandy Play**, öppna den och välj **Ladda ner**. Aktivera **Visa betaversioner** om du vill ha alpha-versionen.
4. Starta om Home Assistant.

### Manuellt

1. Ladda ner `innebandy_play-x.y.z.zip` från [releases](https://github.com/DITT-GITHUB-NAMN/ha-innebandy-play/releases).
2. Packa upp och kopiera mappen `innebandy_play` till `config/custom_components/`.
3. Starta om Home Assistant.

## Konfiguration

1. Gå till **Inställningar → Enheter och tjänster → Lägg till integration** och sök efter *Innebandy Play*.
2. Skriv in lagnamnet, till exempel `Ingarö P2015`, och välj laget i listan.
3. Lägg till fler lag genom att köra samma steg igen. Varje lag får egna sensorer.

### Tabell-ID

Tabellen hämtas med ett ID för seriens grupp. Integrationen försöker hitta det automatiskt, men det går inte alltid att lita på. Så här ställer du in det manuellt:

1. Öppna seriens tabell på play.innebandy.se.
2. Tryck F12, gå till fliken **Nätverk** och sök på `getFromEventReferenceV2`.
3. Kopiera värdet på `eventReference`.
4. Gå till integrationens **Konfigurera** och ange värdet.

Om ID:t är fel visar inställningsdialogen ett felmeddelande.

| Lag | Tabell-ID |
|---|---|
| Ingarö IF P2013 A | 44241 |

## Entiteter

Entiteternas namn bygger på lagnamnet. Exemplen nedan gäller Ingarö IF P2013 A.

| Entitet | Värde | Viktiga attribut |
|---|---|---|
| `sensor.ingaro_if_p2013_a_nasta_match` | Matchtitel | `start`, `location`, `upcoming` |
| `sensor.ingaro_if_p2013_a_pagaende_match` | Ställning, t.ex. `5-6`, eller *Ej startad* | `status`, `period`, `goals`, `penalties`, `timeline`, `goalkeeper_ours` |
| `sensor.ingaro_if_p2013_a_senaste_handelse` | Text för senaste händelsen | `type`, `time`, `period`, `ours` |
| `sensor.ingaro_if_p2013_a_tabellplats` | Placering | `table`, `points`, `played`, `wins`, `draws`, `losses`, `goals`, `goal_diff` |
| `sensor.ingaro_if_p2013_a_resultat` | Senaste resultatet | `form`, `record`, `results` |
| `sensor.ingaro_if_p2013_a_malskyttar` | Namnet på poängligans ledare | `scorers`, `games` |
| `sensor.ingaro_if_p2013_a_trupp` | Antal spelare | `players`, `staff` |
| `binary_sensor.ingaro_if_p2013_a_match_pagar` | På under matchen | `status`, `score`, `title` |

## Kort

Korten använder sensorernas attribut och kräver inga extra integrationer. Byt `co` mot lagets slug, till exempel `ingaro-if-p2013-a`. Slugen står i attributet `company` på valfri sensor för laget.

**Tabell**

```yaml
type: markdown
content: |
  {% set co = 'ingaro-if-p2013-a' %}
  {% set s = states.sensor | selectattr('attributes.company','eq',co) | selectattr('attributes.kind','eq','standings') | first %}
  {% if s and s.attributes.table %}
  **{{ s.attributes.group }}**

  | # | Lag | S | V | O | F | Mål | +/- | P |
  |:-:|:--|:-:|:-:|:-:|:-:|:-:|:-:|:-:|
  {% for r in s.attributes.table -%}
  | {{ r.pos }} | {{ '**' ~ r.team ~ '**' if r.own else r.team }} | {{ r.played }} | {{ r.wins }} | {{ r.draws }} | {{ r.losses }} | {{ r.goals }} | {{ r.goal_diff }} | {{ r.points }} |
  {% endfor %}
  {% else %}
  Tabellen är inte tillgänglig. Kontrollera tabell-ID under integrationens inställningar.
  {% endif %}
```

**Pågående match**

```yaml
type: markdown
content: |
  {% set co = 'ingaro-if-p2013-a' %}
  {% set s = states.sensor | selectattr('attributes.company','eq',co) | selectattr('attributes.kind','eq','current_game') | first %}
  {% set labels = {'not_started': 'Ej startad', 'live': 'Pågår', 'intermission': 'Paus', 'ended': 'Slut'} %}
  {% if s and s.attributes.status in labels %}
  {% set hs = s.attributes.home_score if s.attributes.home_score is not none else '–' %}
  {% set as_ = s.attributes.away_score if s.attributes.away_score is not none else '–' %}
  ### {{ s.attributes.home_team }} {{ hs }} – {{ as_ }} {{ s.attributes.away_team }}
  **{{ labels[s.attributes.status] }}**{% if s.attributes.period %} · Period {{ s.attributes.period }}{% endif %}{% if s.attributes.location %} · {{ s.attributes.location }}{% endif %}

  {% if s.attributes.goalkeeper_home or s.attributes.goalkeeper_away %}
  🧤 {{ s.attributes.home_team }}: {{ s.attributes.goalkeeper_home or '–' }} · {{ s.attributes.away_team }}: {{ s.attributes.goalkeeper_away or '–' }}

  {% endif %}
  {% for e in s.attributes.timeline[:10] %}
  - {{ e.icon }} `{{ e.time or '' }}` {{ e.text }}
  {% else %}
  Inga händelser ännu.
  {% endfor %}
  {% else %}
  Ingen pågående match just nu.
  {% endif %}
```

**Kommande matcher**

```yaml
type: markdown
content: |
  {% set co = 'ingaro-if-p2013-a' %}
  {% set s = states.sensor | selectattr('attributes.company','eq',co) | selectattr('attributes.kind','eq','next_game') | first %}
  ### 📅 Kommande matcher
  {% if s and s.attributes.upcoming %}
  | När | Match | Plats |
  |:--|:--|:--|
  {% for g in s.attributes.upcoming -%}
  | {{ (g.start or '')[:16] | replace('T', ' ') }} | {{ '**' ~ g.title ~ '**' if loop.first else g.title }} | {{ g.location or '–' }} |
  {% endfor %}
  {% else %}
  Inga kommande matcher.
  {% endif %}
```

**Resultat och form**

```yaml
type: markdown
content: |
  {% set co = 'ingaro-if-p2013-a' %}
  {% set s = states.sensor | selectattr('attributes.company','eq',co) | selectattr('attributes.kind','eq','results') | first %}
  {% set icons = {'V': '🟢', 'O': '🟡', 'F': '🔴'} %}
  {% if s and s.attributes.results %}
  ### 📊 Senaste matcher
  Form: {% for f in s.attributes.form %}{{ icons.get(f, f) }}{% endfor %} · {{ s.attributes.record.wins }} V {{ s.attributes.record.draws }} O {{ s.attributes.record.losses }} F

  | Datum | Motståndare | Resultat | |
  |:--|:--|:-:|:-:|
  {% for r in s.attributes.results -%}
  | {{ r.date }} | {{ r.opponent }} {{ '(H)' if r.is_home else '(B)' }} | {{ r.score or '–' }} | {{ icons.get(r.result, '') }} |
  {% endfor %}
  {% else %}
  Inga spelade matcher än.
  {% endif %}
```

**Målskyttar**

```yaml
type: markdown
content: |
  {% set co = 'ingaro-if-p2013-a' %}
  {% set s = states.sensor | selectattr('attributes.company','eq',co) | selectattr('attributes.kind','eq','scorers') | first %}
  {% if s and s.attributes.scorers %}
  ### 🥅 Poängliga
  | Nr | Spelare | Mål | Assist | P |
  |:-:|:--|:-:|:-:|:-:|
  {% for p in s.attributes.scorers -%}
  | {{ p.number or '–' }} | {{ p.name }} | {{ p.goals }} | {{ p.assists }} | {{ p.points }} |
  {% endfor %}
  _Baserat på {{ s.attributes.games }} matcher._
  {% else %}
  Inga mål registrerade ännu.
  {% endif %}
```

**Trupp**

```yaml
type: markdown
content: |
  {% set co = 'ingaro-if-p2015' %}
  {% set s = states.sensor | selectattr('attributes.company','eq',co) | selectattr('attributes.kind','eq','squad') | first %}
  {% if s and s.attributes.players %}
  ### 👥 Trupp ({{ s.state }})
  | Nr | Spelare | |
  |:-:|:--|:-:|
  {% for p in s.attributes.players -%}
  | {{ p.number or '–' }} | {{ p.name }} | {{ '🧤' if p.goalkeeper else '' }} |
  {% endfor %}

  **Ledare:** {% for st in s.attributes.staff %}{{ st.name }} ({{ st.role }}){{ ', ' if not loop.last else '' }}{% endfor %}
  {% else %}
  Truppen är inte tillgänglig.
  {% endif %}
```

Om du vill ha flera kort i en vy, lägg dem i ett `vertical-stack`-kort eller i en sektion med flera kort.

## Automationer

Exemplen använder `notify.mobile_app_din_telefon` och `media_player.kok`. Byt ut dem mot dina egna entiteter.

**Notis vid mål**

```yaml
alias: Innebandy – mål-notis
triggers:
  - trigger: state
    entity_id: sensor.ingaro_if_p2013_a_pagaende_match
    attribute: goals
conditions:
  - condition: template
    value_template: >-
      {{ trigger.to_state.attributes.goals | length > (trigger.from_state.attributes.goals or []) | length }}
actions:
  - action: notify.mobile_app_din_telefon
    data:
      title: "Mål! {{ trigger.to_state.state }}"
      message: >-
        {% set g = trigger.to_state.attributes.goals | last %}
        {{ g.scorer or 'Okänd spelare' }}{% if g.assist %}, assist {{ g.assist }}{% endif %} · P{{ g.period }} {{ g.time }}
```

**Uppläsning av mål**

```yaml
alias: Innebandy – uppläs mål
triggers:
  - trigger: state
    entity_id: sensor.ingaro_if_p2013_a_pagaende_match
    attribute: goals
conditions:
  - condition: template
    value_template: >-
      {{ trigger.to_state.attributes.goals | length > (trigger.from_state.attributes.goals or []) | length }}
actions:
  - action: tts.speak
    target:
      entity_id: tts.home_assistant_cloud
    data:
      media_player_entity_id: media_player.kok
      message: >-
        {% set g = trigger.to_state.attributes.goals | last %}
        {% set lag = trigger.to_state.attributes.home_team if g.side == 'home' else trigger.to_state.attributes.away_team %}
        Mål för {{ lag }}. {{ g.scorer or 'Okänd spelare' }}. Ställningen är {{ trigger.to_state.state | replace('-', ' till ') }}.
mode: queued
```

**Notis vid matchstart**

```yaml
alias: Innebandy – matchstart
triggers:
  - trigger: state
    entity_id: binary_sensor.ingaro_if_p2013_a_match_pagar
    to: "on"
actions:
  - action: notify.mobile_app_din_telefon
    data:
      title: "Matchen har startat"
      message: "{{ trigger.to_state.attributes.title }}"
```

**Notis vid matchslut med resultat**

```yaml
alias: Innebandy – matchslut
triggers:
  - trigger: state
    entity_id: sensor.ingaro_if_p2013_a_pagaende_match
    attribute: status
    to: ended
actions:
  - action: notify.mobile_app_din_telefon
    data:
      title: "Slutresultat {{ trigger.to_state.state }}"
      message: >-
        {% set a = trigger.to_state.attributes %}
        {{ a.home_team }} {{ a.home_score }} – {{ a.away_score }} {{ a.away_team }}
```

## Tjänsten refresh

```yaml
action: innebandy_play.refresh
data:
  company: ingaro-if-p2013-a
```

Utelämna `company` för att uppdatera alla konfigurerade lag.

## Begränsningar

- **Fördröjning:** under matcher kan det ta upp till 30 sekunder innan en händelse syns.
- **Matchfönster:** statistiken hämtas bara från 10 minuter före start till 15 minuter efter beräknat slut.
- **Flera mål mellan två hämtningar:** bara det senaste annonseras.
- **Resultat och målskyttar:** matcher som varken är livesända eller har repris kan saknas.
- **Laguppställning:** API:et visar inte vilka som spelade en enskild match. Sensorn `trupp` visar hela truppen och vem som stod i mål senast.
- **Omstart under match:** gamla händelser annonseras inte, eftersom första inläsningen inte räknas som en förändring.

## Felsökning

1. Öppna **Inställningar → System → Loggar** och filtrera på `innebandy_play`.
2. Ladda ner diagnostiken under integrationens sida. Personuppgifter som spelarnamn är maskerade.
3. Skapa ett ärende under [Issues](https://github.com/DITT-GITHUB-NAMN/ha-innebandy-play/issues) och bifoga diagnostiken.

## Integritet och användning

Integrationen hämtar offentlig matchinformation från solidsport. Den skickar inga personuppgifter. Hämtningarna är glesa utanför matchfönster för att inte belasta tjänsten. Om solidsport eller förbundet vill att hämtningen ändras, öppna ett ärende.

## Licens

MIT. Se [LICENSE](LICENSE).
