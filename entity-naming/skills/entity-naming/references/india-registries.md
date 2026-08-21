# Indian registries — what is checkable, and the fan-out that approximates the rest

## The honest picture

| Register | Automatable? | Why |
|---|---|---|
| Domains (.com/.in/.co.in/.net) | ✅ **Yes, authoritatively** | RDAP is a public structured API. 404 = free, 200 = taken. |
| MCA company/LLP register | 🔴 **No** | Akamai bot protection + JS-rendered search + login. Direct API returns Access Denied. |
| Zaubacorp / Tofler (MCA mirrors) | 🔴 **No** | Cloudflare managed challenge; the checkbox does not pass for automation. |
| IP India trademark register | 🔴 **No** | CAPTCHA-gated, no public API. |

Every one of these was attempted directly during the Ozarva round and blocked.
Do not spend the session rediscovering this — the paths are closed, and the value
of the tooling is in being clear about that rather than shipping a scrape that
silently returns nothing and reads as "clear".

**The only binding MCA check is a CA's RUN or SPICe+ filing.** Everything below is
a research signal that tells you which names are *worth* paying a CA to check.

## The registry-proxy fan-out

Since the register cannot be queried, approximate it with parallel web search and
band the result. This is the step that used to be improvised each session; run it
this way instead so two rounds are comparable.

**Dispatch one agent per batch of 5-8 candidates**, each running these searches:

```
"<Name>" LLP India
"<Name>" private limited India
"<Name>" company Bengaluru OR Karnataka
site:zaubacorp.com "<Name>"
site:tofler.in "<Name>"
"<Name>" trademark India
```

**Each agent returns JSON only** — one object keyed by lowercase slug:

```json
{
  "ozarva":  {"verdict": "watch", "evidence": "no exact company match; 2 phonetically similar names in unrelated sectors"},
  "trisendra": {"verdict": "clean", "evidence": "zero company or trademark matches across all six queries"}
}
```

### Banding rules

Consistency here is what makes scores comparable across rounds, so apply them
literally rather than by feel:

| Verdict | Means | Score contribution |
|---|---|---|
| `clean` | Zero exact matches, few or no similar names | 100 |
| `watch` | No exact match, but several similar names exist | 65 |
| `crowded` | Many similar names, or a same-sector near-match | 30 |
| `blocked` | Exact or near-exact match on the register | 0 |

Feed the merged JSON to `score_names.py --registry`.

### Read the verdicts honestly

A `watch` is not a pass. In the round that produced Ozarva, the chosen name was
banded `watch` — "similar names, no exact" — and there is no record of that ever
being escalated to a binding CA check. That is exactly the gap this fan-out is
supposed to make visible rather than paper over. When you present the board, say
plainly which names are `clean` and which are `watch`, and put the CA filing on
the founder's action list for anything below `clean`.

## Trademark

No API, so this stays a human step — but narrow it before handing it over. Search
IP India on **Wordmark + Phonetic** (phonetic matters more than spelling for
Indian TM objections), in the classes the entity will actually trade in:

| Class | Covers |
|---|---|
| 43 | Restaurants, cafés, food service, accommodation |
| 35 | Retail, business services, co-working |
| 41 | Gyms, fitness, training, entertainment |
| 44 | Salons, wellness, medical |

https://tmrsearch.ipindia.gov.in/eregister/

## Domains: snapshot, not reservation

RDAP tells you a domain was free at the moment you asked. Coined 7-8 letter names
are not under active pressure, but the gap between clearing and buying is the one
window where a good name can be lost for the price of a coffee. When the founder
has a top two or three, buying is the immediate next action, ahead of the CA
filing — the filing takes days, the domain takes minutes.
