# Crustdata schema notes (API version 2025-11-01)

Normalizers (`marketentry/normalizers.py`) may read ONLY the paths listed in sections A–C. Anything absent => `null`.
Source of truth: live responses in `fixtures/raw/` (retrieved 2026-10-31) plus docs.crustdata.com. Status per path:
**V** = seen in a saved live response, **D** = documented but not yet seen live (normalizer tolerates absence; no test depends on it).

## Transport
- Base `https://api.crustdata.com`; headers `Authorization: Bearer`, `x-api-version: 2025-11-01`, `Content-Type: application/json`.
- Credits: response header `X-Credits-Used` (V) on data endpoints; absent on pre-API 429s. Balance: `GET /account/credits` -> `account.credits` (V).
- Rate limit 30 req/min on search/identify/enrich (V headers `x-ratelimit-limit/remaining/reset`). `402` + `error.type=insufficient_credits` (D).
- Error body: `{"error": {"type", "message", "metadata"}}` (D). Client must tolerate non-JSON bodies.

## A. Company record (search `companies[]` item, or enrich/identify `matches[].company_data`)
| Internal field | Path(s) | Status |
|---|---|---|
| company_id | `crustdata_company_id` (fallback `basic_info.crustdata_company_id`) | V |
| name | `basic_info.name` | V |
| domain | `basic_info.primary_domain` | V |
| linkedin_url | `basic_info.professional_network_url` | V |
| description | `basic_info.description` | V |
| employee_range | `basic_info.employee_count_range` | V |
| country | `locations.country` (**alpha-3 in responses**, e.g. `GBR`; filters accept full name) | V (search only; needs `locations` in `fields`) |
| hq_location | `locations.headquarters` | V |
| industry | `taxonomy.professional_network_industry` | D (`basic_info` has NO industries key; null unless `taxonomy` requested) |
| employee_count | `headcount.total` | V |
| headcount_growth_6m | search: `headcount.growth_percent.6m`; enrich: `headcount.growth_percent.six_months` | V |
| headcount_growth_12m | search: `headcount.growth_percent.12m`; enrich: `headcount.growth_percent.yoy` | V |
| open_roles | `hiring.openings_count` (enrich only, `fields` must include `hiring`) | V |
| funding_total | `funding.total_investment_usd` | V |
| last_funding_date | `funding.last_fundraise_date` | V |

Notes: `/company/search` `fields` is a request param; sections not requested are absent. Search `total_count` (int|null) and `next_cursor` (str|null) are top-level (V).
Growth values are percentages (e.g. `6.38` = 6.38%).

## B. Identify / Enrich envelope
- Response is a top-level array, one entry per input: `{matched_on, match_type, matches:[{confidence_score, company_data}]}` (V).
- `match_type` in `domain|name|crustdata_company_id|professional_network_profile_url` (V/D). No match => `matches: []` (D; also handle 404).
- **Name matches are untrusted (V)**: identify `names:["Bits"]` returned BITS Pilani (university) at `confidence_score` 1.0. Accept only when domain or ID agrees.
- Identify costs 0, Enrich 2 credits/company (V). Exactly one identifier array per request, <=25 values.

## C. Person record (`/person/search` `profiles[]`)
| Internal field | Path | Status |
|---|---|---|
| person_id | `crustdata_person_id` | V |
| name | `basic_profile.name` | V |
| headline | `basic_profile.headline` | V |
| current_title | `basic_profile.current_title` (fallback `experience.employment_details.current[].title`) | V |
| employer list | `experience.employment_details.current[]` (list) | V |
| employer name | `current[].name` | V |
| employer company id | `current[].crustdata_company_id` | V |
| employer website | `current[].company_website` (domain derived by stripping scheme/www/path) | V |
| employment_start | `current[].start_date` (often null) | V |
| linkedin_url | not seen in fixtures | — (null + flag `linkedin_url_missing`) |

Never read or store email/phone fields (`business_email_verified` etc. are ignored by design).
Person filters (D): `experience.employment_details.current.company_website_domain` (V works), `...current.title` with `(.)` (D), `...current.company_name`. No company-ID filter documented; verify employer via `current[].crustdata_company_id`.
Person Search cost ~0.23/result with default fields; empty results free (V: 0.69 for 3).

## D. Web
- `POST /web/search/live` `{query, location(ISO2), sources[], page}` -> `{success, results[{source,title,url,snippet,position}], metadata.total_results}` (V). 1 credit/query. **URLs are Google `goto?url=` redirects** (V); store as given.
- `POST /web/enrich/live` `{urls[<=10]}` -> array `{success,url,timestamp,title,content}` (D), 1 credit/page.

## E. Still unverified (do not code against)
Person Enrich body/shape, Web Fetch live shape, Job Search, cursor pagination across pages, `taxonomy.categories = "FinTech"` as a filter, 429 body.
