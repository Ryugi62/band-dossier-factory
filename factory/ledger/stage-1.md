# Requirement ledger — dossier stage 1

Source: `sf-2026/challenges/dossier/spec/stage-1.md` (all 680 lines) plus planner decisions D1–D8
(`factory/decisions.md`). Written by the verifier from the specification only; the shipped checks
were not opened.

## How to run every probe (one command)

```sh
factory/probes/stage-1/run_all.sh /path/to/result-repo-checkout
```

It builds `stage-1/` from its `Dockerfile` and the mock web from
`sf-2026/challenges/dossier/web`, starts both on an `--internal` docker network (no outbound
access), mounts the sample corpus plus the verifier corpus (`factory/probes/stage-1/corpus/`),
runs `run.py` from a `python:3.12-slim` container on that network, prints one line per probe and
`TOTAL: n passed, m failed`, and exits non-zero on any failure. Environment overrides:
`SF_ROOT` (default `<workdir>/sf-2026`), `PROBE_ONLY=P06,P11` (subset),
`KEEP=1` (leave containers up).

Against an already running service (no docker orchestration):

```sh
python3 factory/probes/stage-1/run.py --service http://127.0.0.1:8000 \
  --mock http://127.0.0.1:8080 --admin local-admin --corpus <merged corpus dir>
```

`python3 factory/probes/stage-1/test_appendix_a.py` self-tests the verifier's Appendix A oracle
(no service needed); `run.py` runs it first.

## Columns

- **ID**: `R<section>-<nn>`; `RA-` is Appendix A, `RD-` a planner decision.
- **★**: a row a quick reading would miss (implied consequence, default, boundary,
  cross-section interaction).
- **Kind**: behaviour, error, limit, format, timing, concurrency, retry, state, cost, delivery,
  support, export-state, reading (checked by reading the diff/image, not by HTTP).
- **Probe**: probe IDs in `factory/probes/stage-1/run.py`. `G` = the global response checks
  applied to every response of every probe; `INV` = the dossier invariant checker applied to
  every dossier/list read; `EV` = the evidence oracle; `LOG` = mock call-log checks.
  `read` = verified by reading the code/image at verification time.

## §1 Scope

| ID | ★ | Section | Requirement (verbatim) | Kind | Probe |
|---|---|---|---|---|---|
| R1-01 | | §1 | "A caller asks for a company by its web domain. The service researches the company on the web and keeps a **dossier**: a profile of six fields, each with the value the web supports and the excerpts it came from." | behaviour | P06, P07 |
| R1-02 | | §1 | "A dossier is built in the background, read any number of times, and refreshed on request." | behaviour | P06, P10 |
| R1-03 | | §1 | "Only the HTTP API is required." | delivery | read |
| R1-04 | ★ | §1 | "The following apply to all operations, including concurrent requests and retries:" | concurrency | INV in P11, P13 |
| R1-05 | ★ | §1 | "Every value the service asserts cites at least one excerpt that a provider endpoint served to this service, and that excerpt supports the value." | support | INV + served-text check (end of run), P07 |
| R1-06 | ★ | §1 | "No citation is invented, reworded, or attached to a value it does not support." | support | INV + served-text check |
| R1-07 | | §1 | "No build of a dossier spends more than 80 units (§9)." | cost | LOG in P06, P07, P08, P10, P17 |
| R1-08 | | §1 | "Contact data, people search, and fields other than the six in §4 are out of scope." | behaviour | INV (exactly six fields) |

## §2 Delivery and deployment

| ID | ★ | Section | Requirement (verbatim) | Kind | Probe |
|---|---|---|---|---|---|
| R2-01 | | §2 | "Deliver an HTTP service, a `Dockerfile` and a `RUN.md` with a command that builds and starts the service without manual setup." | delivery | run_all.sh (build), read |
| R2-02 | | §2 | "Language, framework and storage are unrestricted. A `docker-compose.yml` is optional." | delivery | read |
| R2-03 | | §2 | "The submitted `Dockerfile` is built and started, and only its HTTP behavior is exercised; it does not import or execute the submission's source files on the host that runs it." | delivery | run_all.sh |
| R2-04 | ★ | §2 | "The image must run on its own with `-e PORT=<port>` and a port mapping." | delivery | run_all.sh (only PORT + provider vars) |
| R2-05 | | §2 | "All runtime dependencies, initialization and seed data must work within that single container. Compose configuration is not used to start the service." | delivery | run_all.sh |
| R2-06 | | §2 Web access | "Nimble is the default provider: every service must be able to research companies using Nimble alone." | behaviour | P07, P09 (tavily faulted) |
| R2-07 | ★ | §2 Web access | "Tavily is optional: a service may use it beside Nimble, and its absence must not prevent research while Nimble answers." | behaviour | P09 (tavily error fault → build still `ready`) |
| R2-08 | | §2 Web access | "The service reaches the providers only through WebRouter, the Python package `webrouter` (module `web_router`)." | delivery | read |
| R2-09 | | §2 Web access | "every request to a provider goes through `web_router`: called in-process, or from a Python helper process that the service runs inside its own container." | delivery | read |
| R2-10 | | §2 Web access | "The stage folder's dependency manifest lists `webrouter>=0.12.0`." | delivery | read |
| R2-11 | | §2 Web access | "Calling a provider's API by any other route is not permitted." | delivery | read |
| R2-12 | | §2 Web access | "Install it and the provider SDK dependencies from PyPI, including in the service's Docker build: `pip install \"webrouter[search,extract,research]>=0.12.0\"`" | delivery | read (Dockerfile) |
| R2-13 | | §2 env | "`PORT` — The port to listen on (§3.1)" | delivery | run_all.sh |
| R2-14 | | §2 env | "`NIMBLE_API_KEY` — Credential for the `nimble` provider" | delivery | run_all.sh |
| R2-15 | | §2 env | "`NIMBLE_BASE_URL` — Base URL of the `nimble` provider endpoint" | delivery | run_all.sh (mock URL honoured: LOG shows calls) |
| R2-16 | | §2 env | "`TAVILY_API_KEY` — Credential for the `tavily` provider" | delivery | run_all.sh |
| R2-17 | | §2 env | "`TAVILY_BASE_URL` — Base URL of the `tavily` provider endpoint" | delivery | run_all.sh; LOG (any tavily call must reach the mock) |
| R2-18 | | §2 env | "Keys are opaque non-empty strings." | delivery | run_all.sh (keys = `local`) |
| R2-19 | | §2 env | "A service that uses Tavily passes its base URL to WebRouter in `provider_config`" | delivery | read |
| R2-20 | | §2 limits | "CPU — 2 vCPU" | limit | run_all.sh (`--cpus 2`) |
| R2-21 | | §2 limits | "Memory — 3 GiB" | limit | run_all.sh (`--memory 3g`) |
| R2-22 | | §2 limits | "Start to first healthy response — 60 s" | timing | P00 |
| R2-23 | ★ | §2 limits | "Concurrent requests — up to 50 in flight" | concurrency | P13 |
| R2-24 | ★ | §2 limits | "Per-request timeout — 5 s (10 s for `POST /_test/reset`)" | timing | G (client timeout 5 s; 10 s for reset/export/import) |
| R2-25 | ★ | §2 limits | "Outbound network — available during `docker build`; at run time, **only the provider endpoints this specification lists**" | limit | run_all.sh (`--internal` network) |
| R2-26 | | §2 limits | "Disk — ephemeral; state need not survive a container restart" | state | — (permission, nothing to probe) |
| R2-27 | ★ | §2 limits | "Runtime assets and dependencies must be included in the image. This includes fonts, scripts and stylesheets; external services other than the provider endpoints this specification lists are unavailable at runtime." | delivery | run_all.sh (`--internal`), read |

## §3 Runtime contract

| ID | ★ | Section | Requirement (verbatim) | Kind | Probe |
|---|---|---|---|---|---|
| R3-01 | | §3.1 | "Listen on `0.0.0.0` using the `PORT` environment variable" | delivery | run_all.sh (PORT=8080 reached from another container) |
| R3-02 | ★ | §3.1 | "default `8080`" | delivery | read (default when PORT unset) |
| R3-03 | | §3.2 | "`GET /health  ->  200  {\"status\": \"ok\"}`" | format | P00 |
| R3-04 | | §3.2 | "Return 200 once the service and its data store can serve requests, within 60 seconds of container start." | timing | P00 |
| R3-05 | | §3.2 | "Non-200 responses are permitted before the service is ready." | behaviour | P00 (tolerated while waiting) |
| R3-06 | ★ | §3.2 | "`/health` makes no provider call." | cost | P00 (LOG unchanged) |
| R3-07 | | §3.3 | "`POST /_test/reset` … `->  204 No Content`" | format | P01 |
| R3-08 | | §3.3 | "Replace all service state with the fixture in the request body (§4)." | state | P01 |
| R3-09 | ★ | §3.3 | "When reset returns 204, subsequent requests must see only that fixture: no users other than the seeded ones" | state | P01 (pre-reset signup → login 401) |
| R3-10 | ★ | §3.3 | "no dossiers" | state | P01 (list empty, GET 404) |
| R3-11 | ★ | §3.3 | "and no stored idempotent responses." | state | P01 (same key after reset is a first use: 202, not 200) |
| R3-12 | | §3.3 | "Repeated resets are supported." | behaviour | P01 |
| R3-13 | ★ | §3.3 | "A build still running when reset is called must not change the state that follows the reset." | concurrency | P14 |
| R3-14 | | §3.3 | "This control endpoint must be enabled in the delivered image and requires no authentication." | behaviour | P01 |
| R3-15 | ★ | §3.4 | "The service keeps a clock that only reset and `POST /_test/clock` move." | timing | P02 (researched_at equals clock after real seconds pass) |
| R3-16 | ★ | §3.4 | "Every timestamp the service records or returns is read from this clock." | timing | P02, P06 (researched_at == clock) |
| R3-17 | | §3.4 | "`POST /_test/clock` `{ \"now\": … }` `->  204 No Content`" | format | P02 |
| R3-18 | | §3.4 | "Reset sets the clock to the fixture's `now`." | timing | P02 |
| R3-19 | ★ | §3.4 | "Before the first reset the clock follows the system time." | timing | P00 (pre-reset build: researched_at within 5 min of host UTC) |
| R3-20 | ★ | §3.4 | "The clock stands still between calls: two requests with no clock call between them read the same time." | timing | P02 |
| R3-21 | | §3.4 | "`now` is an RFC 3339 timestamp with an explicit offset." | format | P02 (no offset → 422) |
| R3-22 | ★ | §3.4 | "A `now` earlier than the clock's current time is 422 `validation_failed` and changes nothing." | error | P02 (equal `now` accepted; earlier → 422; clock unchanged) |
| R3-23 | | §3.4 | "`POST /_test/clock` requires no authentication." | behaviour | P02 |
| R3-24 | | §3.5 | "Requests and responses are `application/json; charset=utf-8`." | format | G |
| R3-25 | | §3.5 | "Timestamps in responses are RFC 3339 with an explicit offset" | format | INV |
| R3-26 | ★ | §3.5 | "Unknown fields in a request body are ignored, never an error." | behaviour | P03, P11 |
| R3-27 | ★ | §3.5 | "Unknown query parameters are ignored." | behaviour | P03, P12 |
| R3-28 | | §3.5 | "IDs are opaque strings of at most 64 characters. Their format is yours." | format | INV, P04 |

## §4 Model

| ID | ★ | Section | Requirement (verbatim) | Kind | Probe |
|---|---|---|---|---|---|
| R4-01 | ★ | §4 Users | "Every authenticated user sees the same dossiers." | behaviour | P04 |
| R4-02 | | §4 Domains | "A company is identified by its domain." | behaviour | P05 |
| R4-03 | ★ | §4 Domains | "Every domain the API takes, in a body or a path, is first **normalised**: surrounding whitespace removed" | format | P05 |
| R4-04 | | §4 Domains | "lowercased" | format | P05 |
| R4-05 | ★ | §4 Domains | "one trailing `.` removed" | format | P05 (`acme.test..` → 422) |
| R4-06 | ★ | §4 Domains | "and one leading `www.` removed." | format | P05 (`www.www.x.test` → `www.x.test`, valid) |
| R4-07 | | §4 Domains | "two or more labels separated by `.`" | error | P05 |
| R4-08 | ★ | §4 Domains | "each label 1 to 63 characters of `a-z`, `0-9` and `-`" | error | P05 (63 ok, 64 → 422, empty label → 422, `_` → 422) |
| R4-09 | | §4 Domains | "not starting or ending with `-`" | error | P05 |
| R4-10 | ★ | §4 Domains | "and 253 characters or fewer in total." | error | P05 (253 ok → 404; 254 → 422) |
| R4-11 | | §4 Domains | "Anything else, including a URL with a scheme or a path, is 422 `validation_failed`." | error | P05 |
| R4-12 | | §4 Domains | "`Acme-Robotics.TEST.`, `www.acme-robotics.test` and `acme-robotics.test` name the same company and the same dossier." | behaviour | P05 |
| R4-13 | | §4 Domains | "Responses always carry the normalised domain." | format | P05, INV |
| R4-14 | | §4 Fields | "A dossier has exactly these six fields" | format | INV |
| R4-15 | | §4 Fields | "`legal_name` — String: the company's registered name" | format | INV, EV |
| R4-16 | | §4 Fields | "`hq_city` — String: the city of the company's headquarters, without region or country" | format | INV, EV |
| R4-17 | | §4 Fields | "`ceo` — String: the full name of the company's chief executive" | format | INV, EV |
| R4-18 | | §4 Fields | "`founded_year` — Integer: the year the company was founded" | format | INV (JSON integer) |
| R4-19 | | §4 Fields | "`headcount_range` — String: one of `1-10`, `11-50`, `51-200`, `201-500`, `501-1000`, `1001-5000`, `5001-10000`, `10001+`" | format | INV |
| R4-20 | | §4 Fields | "`funding_total` — Integer: total equity funding raised, in whole US dollars" | format | INV (JSON integer) |
| R4-21 | ★ | §4 Fields | "A string value is written as the supporting excerpt writes it, without surrounding whitespace." | format | INV (value equals oracle value of each citation, no surrounding whitespace) |
| R4-22 | ★ | §4 Fields | "A headcount the web states as a number, or as a range that fits inside one of the ranges above, has the range that contains it as its value." | format | INV, P06 (zephyr "between 60 and 150" → 51-200) |
| R4-23 | | §4 Field shape | "`status` is `known` when `value` is not null, and `unknown` when it is." | format | INV |
| R4-24 | | §4 Field shape | "A `known` field has one or more citations." | format | INV |
| R4-25 | | §4 Field shape | "An `unknown` field has `\"value\": null` and `\"citations\": []`." | format | INV |
| R4-26 | ★ | §4 Field shape | "`url` is the URL of the page the excerpt was served for" | support | served-text check |
| R4-27 | ★ | §4 Field shape | "`provider` is `nimble` or `tavily`, the provider that served it." | support | INV + served-text check (provider of the serving call) |
| R4-28 | ★ | §4 Evidence | "The **evidence** for a company is every page that some search, through any provider and for any query naming the company (as in Appendix A.2), returns, with its full text, and every claim that a `nimble` research run for the company asking for all six fields answers with." | support | EV in P06, P07 |
| R4-29 | ★ | §4 Evidence | "Of the searches that a provider answers without an error, every build makes exactly one whose query is exactly the company's normalised domain, through a provider of its choice" | cost | LOG (exactly one status-200 search with query == domain per build), P18 |
| R4-30 | ★ | §4 Evidence | "its other such searches use other queries." | cost | LOG |
| R4-31 | ★ | §4 Evidence | "A search that a provider answers with an error does not count." | retry | P18 |
| R4-32 | | §4 Evidence | "The pages whose text a build obtains from providers are the pages it **gathers**." | behaviour | — (definition) |
| R4-33 | ★ | §4 Citation | "The excerpt is copied character for character from that served text, except that any run of whitespace may be written as a single space." | support | served-text check |
| R4-34 | ★ | §4 Citation | "It is 1 to 500 characters long." | limit | INV |
| R4-35 | ★ | §4 Citation | "It is taken from the page's prose (below), not from its header." | support | served-text check (prose only), P06 (Facts-header trap: hq_city must be Zürich, not Berlin) |
| R4-36 | | §4 Support | "An excerpt **supports** a value when, read on its own, it states that value for that field of this company, as Appendix A defines." | support | INV (oracle) |
| R4-37 | | §4 Support | "The excerpt may write the value differently from the API" | support | INV, P06 ($12.5 million → 12500000) |
| R4-38 | ★ | §4 Support | "A research answer carries a claimed value for a field and a citation for the claim. The claim is asserted only when its citation supports it." | support | P07 (nordlicht research claims: unsupported funding/headcount claims stay unknown; quillmate/ferncliff sample claims) |
| R4-39 | ★ | §4 Support | "A field is `unknown` when no evidence supports a value for it, even when a research answer claims one." | support | P07 (nordlicht), EV |
| R4-40 | ★ | §4 Support | "When the evidence supports more than one value for a field, the field holds one of them and cites only excerpts that support that value." | support | INV (every citation supports the held value), P07 (halvorsen hq Valencia/Utrecht, pemberton Galway/Leeds, brightwater funding) — any supported value accepted (D3) |
| R4-41 | ★ | §4 + §8 | (consequence of R4-28 with "each field is `known` exactly when the evidence (§4) supports a value") a field supported by a sentence of a searchable page of the company, or by a supported research claim, must be `known`. | support | EV in P06, P07, P10 |
| R4-42 | | §4 Pages | "Every page has a URL, a title and a text. A text may begin with **header lines**, each of the form `Name: value`, where the name is a capitalised word or several joined by `-`." | format | served-text check (header split) |
| R4-43 | | §4 Pages | "The header ends at the first empty line; everything after it is the page's **prose**." | format | served-text check |
| R4-44 | ★ | §4 Pages | "A text whose first line is not a header line has no header and is all prose." | format | served-text check (lite snippets are prose) |
| R4-45 | ★ | §4 Pages | "The header line `Facts:` carries a JSON object … It is informative only: citations come from the prose, and whether an excerpt supports a value is decided by Appendix A alone." | support | P06 (Facts trap), served-text check |
| R4-46 | | §4 Pages | "The service may ignore other header lines." | behaviour | — (permission) |
| R4-47 | ★ | §4 Fixture | "`now` is required and sets the clock (§3.4)." | error | P01 (missing now → 422), P02 |
| R4-48 | | §4 Fixture | "Seeded users must be able to log in with the given password immediately." | behaviour | P01 |
| R4-49 | ★ | §4 Fixture | "A fixture with two users sharing an email is a reset error: 422 `validation_failed`, changing nothing." | error | P01 (state before the bad reset still there) |

## §5 Errors

| ID | ★ | Section | Requirement (verbatim) | Kind | Probe |
|---|---|---|---|---|---|
| R5-01 | | §5 | "Every 4xx and 5xx response carries this body: `{ \"error\": { \"code\": …, \"message\": … } }`" | format | G |
| R5-02 | | §5 | "Use the specified HTTP status and `code`. The human-readable `message` may use any wording." | format | G + every error assertion |
| R5-03 | | §5 table | "400 `malformed_request` — Unparseable body, or a field of the wrong JSON type" | error | P01, P04, P05, P15 |
| R5-04 | | §5 table | "400 `missing_idempotency_key` — Required `Idempotency-Key` header absent or empty" | error | P11 |
| R5-05 | | §5 table | "401 `unauthenticated` — Missing, malformed or unknown bearer token" | error | P04 |
| R5-06 | | §5 table | "404 `not_found` — No such resource, or not visible to this caller" | error | P05, P06, P10 |
| R5-07 | | §5 table | "409 `idempotency_key_reuse` — Key already used by this caller with a different request body" | error | P11 |
| R5-08 | | §5 table | "422 `validation_failed` — A required field or query parameter is missing, or a stated rule is violated with no more specific code" | error | P04, P05, P12 |
| R5-09 | ★ | §5 | "A field of the correct JSON type with an invalid format or out-of-range value gives 422 `validation_failed`, unless an endpoint specifies a different error." | error | P04, P05 |
| R5-10 | ★ | §5 | "An integer-valued **query parameter** is written as plain decimal digits: `1e9`, `4.0` and `+4` are 422 `validation_failed` whatever their numeric value." | error | P12 |
| R5-11 | ★ | §5 | "Reserve 400 `malformed_request` for a body that does not parse or a field of the wrong type." | error | P04, P05 (wrong type → 400, bad value → 422) |
| R5-12 | ★ | §5 ranges | "`Idempotency-Key` — 1 to 255 characters — 422 `validation_failed`" | limit | P11 (255 ok, 256 → 422) |
| R5-13 | ★ | §5 ranges | "`limit` — integer 1 to 200 — 422 `validation_failed`" | limit | P12 (0, 201 → 422; 1, 200 ok) |
| R5-14 | ★ | §5 ranges | "`offset` — integer 0 or more — 422 `validation_failed`" | limit | P12 |
| R5-15 | ★ | §5 | "Requests must not produce 5xx responses, including under concurrent load and when a provider endpoint answers with an error." | error | G, P09, P13 |

## §6 Authentication

| ID | ★ | Section | Requirement (verbatim) | Kind | Probe |
|---|---|---|---|---|---|
| R6-01 | | §6 | "`POST /auth/signup` … `->  201  { \"user_id\": \"u_1\", \"display_name\": \"Ada\", \"token\": \"...\" }`" | format | P04 |
| R6-02 | | §6 | "`POST /auth/login` … `->  200  { \"user_id\": \"u_1\", \"display_name\": \"Ada\", \"token\": \"...\" }`" | format | P04 |
| R6-03 | ★ | §6 | "Email already registered — 409 `email_taken`" | error | P04 (incl. seeded email; concurrent signup burst → exactly one 201) |
| R6-04 | ★ | §6 | "Password shorter than 8 characters — 422 `validation_failed`" | error | P04 (7 → 422, 8 → 201) |
| R6-05 | | §6 | "`email` not of the form `local@domain` — 422 `validation_failed`" | error | P04 |
| R6-06 | ★ | §6 | "`display_name` empty or longer than 100 characters — 422 `validation_failed`" | error | P04 (100 ok, 101 → 422, "" → 422) |
| R6-07 | | §6 | "Wrong password or unknown email on login — 401 `unauthenticated`" | error | P04 |
| R6-08 | ★ | §6 | "For a user seeded by the fixture (§3.3), `user_id` is that user's `id` in the fixture." | format | P01 |
| R6-09 | | §6 | "Every other endpoint requires a bearer token, except `/health`, the `/_test/*` endpoints and the two above." | behaviour | P04, P01, P02, P15 |
| R6-10 | ★ | §6 | "A request to such an endpoint that lacks a valid token is 401 `unauthenticated`, even when it also lacks a required `Idempotency-Key`." | error | P04 |
| R6-11 | | §6 | "Tokens do not expire." | behaviour | P04 (token valid after clock +400 days) |
| R6-12 | ★ | §6 | "An account may have multiple valid tokens and concurrent sessions." | behaviour | P04 |
| R6-13 | ★ | §6 | "Passwords must be stored using a password-hashing function such as bcrypt, scrypt or Argon2, or an equivalent. Plaintext password storage is not permitted." | state | P15 (export never contains a plaintext password), read |

## §7 Idempotency

| ID | ★ | Section | Requirement (verbatim) | Kind | Probe |
|---|---|---|---|---|---|
| R7-01 | | §7 | "Two write paths require an idempotency key (§8): **`POST /dossiers`** and **`POST /dossiers/{domain}/refresh`**. Everything below applies to each of them independently." | retry | P11 |
| R7-02 | ★ | §7 | "The key is scoped to **the authenticated user**. Two different users may use the same key string with no interaction between them." | retry | P11 |
| R7-03 | | §7 | "A replay means the same user sending the **same method, the same path and the same body**." | retry | P11 |
| R7-04 | ★ | §7 | "The same key with the same body on a different path is a different request, not a replay, and must succeed normally." | retry | P11 (POST /dossiers key K then refresh key K → 202) |
| R7-05 | ★ | §7 | "`Acme-Robotics.test` and `acme-robotics.test` in a path or body are different requests for this rule, though they name the same dossier." | retry | P11 (body → 409; path → normal 202) |
| R7-06 | | §7 table | "Header absent or empty — 400 `missing_idempotency_key`" | error | P11 |
| R7-07 | | §7 table | "First use of the key — The normal response (§8)" | retry | P11 |
| R7-08 | ★ | §7 table | "Replay: same key, same body — **200**, body identical to the original response as a JSON value" | retry | P11 (original 202 → replay 200), RD-06 |
| R7-09 | | §7 table | "Same key, different body — 409 `idempotency_key_reuse`" | error | P11 |
| R7-10 | ★ | §7 table | "Key reused after the original request failed with 4xx — Treated as a first use" | retry | P11 |
| R7-11 | ★ | §7 | "\"Same body\" means the same JSON value after parsing — key order and whitespace do not matter." | retry | P11 (raw bodies with different order/spacing) |
| R7-12 | ★ | §7 | "Unknown fields are ignored (§3.5) and play no part in this comparison: a body that differs from the first only in unknown fields is the same body, so the request is a replay." | retry | P11 |
| R7-13 | ★ | §7 | "`POST /dossiers/{domain}/refresh` takes no body; any body sent to it is ignored and plays no part in deciding a replay." | retry | P11 |
| R7-14 | ★ | §7 | "For concurrent identical requests with an unused key, exactly one returns the normal response. The others return 200 with the same body. The operation takes effect only once." | concurrency | P11 (burst of 20 identical POSTs; LOG one build) |
| R7-15 | ★ | §7 | "A successful replay returns the original response, even after the dossier has changed." | retry | P11 (replay after build finished still shows `building`) |
| R7-16 | ★ | §7 | "It starts no build and makes no provider call." | cost | P11 (LOG unchanged) |
| R7-17 | ★ | §7 | "After the body has parsed as a JSON object and the caller is authenticated, an already claimed key is resolved before field validation. Thus changing a successful request to an invalid body with the same key still returns `409 idempotency_key_reuse`." | error | P11 |

## §8 API

| ID | ★ | Section | Requirement (verbatim) | Kind | Probe |
|---|---|---|---|---|---|
| R8-01 | | §8 Builds | "A **build** researches one dossier: it calls the providers, decides each field, and replaces the dossier's fields with the result when it completes." | behaviour | P06, P10 |
| R8-02 | | §8 Builds | "A dossier's first build starts with `POST /dossiers`, and every later one with `POST /dossiers/{domain}/refresh`." | behaviour | P06, P10 |
| R8-03 | ★ | §8 Builds | "A build's **time** is the clock's time when the request that started it was received." | timing | P02 (clock moved during build; researched_at = time of POST), P10 |
| R8-04 | ★ | §8 Builds | "A dossier has at most one build running at a time." | concurrency | P10, P11 (LOG: one research run / one domain search per window) |
| R8-05 | | §8 Builds | "A build ends in `ready` when it completed" | state | P06, P07 |
| R8-06 | ★ | §8 Builds | "or `failed` when none of its provider calls succeeded." | state | P09 (all nimble methods faulted → failed; only research faulted → ready) |
| R8-07 | ★ | §8 Builds | "A failed build leaves the fields as they were." | state | P09 (fields and researched_at unchanged) |
| R8-08 | ★ | §8 Builds | "When a build completes `ready`, each field is `known` exactly when the evidence (§4) supports a value for it." | support | EV in P06, P07, P08, P10 |
| R8-09 | ★ | §8 Builds | "A build whose provider calls each answer within one second ends within 10 seconds of the request that started it." | timing | P06, P07 (no delay), P17 (0.8 s delay on every nimble method) |
| R8-10 | | §8 Builds | "Against the live providers (`NIMBLE_BASE_URL` unset, or its host `sdk.nimbleway.com`) … a build does not give up on a call that has been waiting less than 30 seconds" | timing | read |
| R8-11 | | §8 Builds | "nor stop gathering because of the time it has run in its first 120 seconds." | timing | read |
| R8-12 | | §8 Builds | "It still ends `ready` or `failed` within 300 seconds." | timing | read |
| R8-13 | ★ | §8 Builds | "Reading a dossier, listing dossiers and every other request except `POST /dossiers` and `POST /dossiers/{domain}/refresh` make no provider call." | cost | P06, P11, P15 (LOG unchanged across reads, auth, export, import, replay) |
| R8-14 | | §8 POST /dossiers | "`Idempotency-Key` is required; see §7." | error | P11 |
| R8-15 | | §8 POST /dossiers | "`202 { \"dossier_id\": \"d_7\", \"domain\": \"acme-robotics.test\", \"state\": \"building\" }`" | format | P06 |
| R8-16 | | §8 POST /dossiers | "When no dossier exists for the domain, the service creates one, starts its first build and returns 202." | behaviour | P06 |
| R8-17 | ★ | §8 POST /dossiers | "When a dossier already exists for the domain, the service starts no build and returns **200** with that dossier's `dossier_id`, `domain` and current `state`." | behaviour | P06 (LOG unchanged; state `ready`), P11 |
| R8-18 | ★ | §8 POST /dossiers | "Concurrent requests for the same domain create one dossier and start one build, whatever their keys." | concurrency | P11 (burst of 20 distinct keys → one 202, one dossier_id, LOG one build) |
| R8-19 | | §8 POST /dossiers | "`domain` missing — 422 `validation_failed`" | error | P05 |
| R8-20 | | §8 POST /dossiers | "`domain` invalid after normalisation (§4) — 422 `validation_failed`" | error | P05 |
| R8-21 | | §8 GET | response shape `dossier_id`, `domain`, `state`, `researched_at`, `spent_units`, `fields` | format | INV |
| R8-22 | | §8 GET | "`state` is `building` while a build runs, otherwise the outcome of the latest build, `ready` or `failed`." | state | P06, P09, P10 |
| R8-23 | | §8 GET | "`fields` always holds all six fields." | format | INV |
| R8-24 | ★ | §8 GET | "Before the first build completes `ready`, every field is `unknown`." | state | P06 (read while building), P09 (failed first build) |
| R8-25 | ★ | §8 GET | "While a later build runs, `fields` are those of the last build that completed `ready`." | state | P10 |
| R8-26 | ★ | §8 GET | "`researched_at` is the time of the last build that completed `ready`, or null." | state | P06, P09, P10 |
| R8-27 | ★ | §8 GET | "`spent_units` is the total cost (§9) of every provider call made for this dossier, by every build, since it was created." | cost | LOG (spent_units == sum of log costs of the build windows; cumulative over refreshes), RD-04 |
| R8-28 | | §8 GET | "The domain in the path is normalised (§4). No dossier for it is 404 `not_found`." | error | P05 |
| R8-29 | | §8 refresh | "`Idempotency-Key` is required; see §7. No body." | error | P11 |
| R8-30 | | §8 refresh | "Starts a new build of the dossier and returns 202 with `{ \"dossier_id\", \"domain\", \"state\": \"building\" }`." | format | P10 |
| R8-31 | ★ | §8 refresh | "A refresh received while a build of the dossier is running starts no second build and returns 202 with the same body." | concurrency | P10 (burst of 10 refreshes with distinct keys) |
| R8-32 | ★ | §8 refresh | "A refresh researches again: its build makes provider calls whether or not anything has changed since the last build, and its spending counts in `spent_units`." | cost | P10 (LOG non-empty, spent_units grows) |
| R8-33 | | §8 refresh | "No dossier for the domain — 404 `not_found`" | error | P10 |
| R8-34 | ★ | §8 refresh | (with §4) a refresh whose path domain is invalid after normalisation is 422 `validation_failed` | error | P05 |
| R8-35 | | §8 list | response shape `{ "dossiers": [ { dossier_id, domain, state, legal_name, researched_at, spent_units } ], "has_more" }` | format | INV, P12 |
| R8-36 | | §8 list | "`legal_name` is the value of the dossier's `legal_name` field, or null." | format | P12 |
| R8-37 | ★ | §8 list | "`q` is optional. When present, only dossiers whose domain or `legal_name` contains `q`, compared case-insensitively, are listed." | behaviour | P12 (q matching only legal_name; upper-case q) |
| R8-38 | ★ | §8 list | "An empty `q` lists every dossier." | behaviour | P12 |
| R8-39 | | §8 list | "Dossiers are ordered by domain ascending." | behaviour | P12 |
| R8-40 | ★ | §8 list | "`limit` defaults to 50, range 1 to 200." | limit | P12 (51+ dossiers → 50 returned, has_more true) |
| R8-41 | ★ | §8 list | "`offset` defaults to 0." | limit | P12 |
| R8-42 | ★ | §8 list | "`has_more` is true when items exist beyond the last one returned." | behaviour | P12 |

## §9 Providers and cost

| ID | ★ | Section | Requirement (verbatim) | Kind | Probe |
|---|---|---|---|---|---|
| R9-01 | | §9 | "Search through `nimble`, depth `lite` (title, URL and snippet) — 1" | cost | LOG (spent_units == log cost sum) |
| R9-02 | | §9 | "Search through `nimble`, depth `fast` (a truncated page body) — 5" | cost | LOG |
| R9-03 | | §9 | "Search through `nimble`, depth `deep` (the full page) — 15" | cost | LOG |
| R9-04 | | §9 | "Search through `tavily`, depth `lite` — 8" | cost | LOG |
| R9-05 | | §9 | "Search through `tavily`, depth `fast` — 16" | cost | LOG |
| R9-06 | | §9 | "Search through `tavily`, depth `deep` (the full page) — 16" | cost | LOG |
| R9-07 | ★ | §9 | "Extract through `nimble` — 1 per URL requested, including a URL for which no page is returned" | cost | LOG |
| R9-08 | ★ | §9 | "Extract through `tavily` — 2 per URL requested, including a URL for which no page is returned" | cost | LOG |
| R9-09 | ★ | §9 | "Research run through `nimble` — 25 when the run is started; checking on or collecting a run costs nothing" | cost | LOG |
| R9-10 | | §9 | "A search's depth is WebRouter's `search_depth`." | cost | LOG |
| R9-11 | | §9 | "A search returns at most 10 results, whatever number it asks for." | behaviour | — (provider property) |
| R9-12 | ★ | §9 | "A call that a provider refuses with an error status costs nothing." | cost | P09 (all faulted → spent_units 0) |
| R9-13 | ★ | §9 | "A call whose answer does not arrive, because it times out or its connection fails, costs its units as in the table, whether or not the provider received it." | cost | P17 (delays; spent_units == log cost), read |
| R9-14 | ★ | §9 | "An extract that the provider answers with no page for the URL is not refused: it costs its units, as in the table, whatever status says so." | cost | LOG, read |
| R9-15 | ★ | §9 | "An extract through `nimble` does not set `render`." | cost | LOG (every nimble extract costs exactly len(urls)) |
| R9-16 | ★ | §9 | "A build stops making provider calls before its spending would exceed 80 units, and completes with the pages and research claims it has obtained." | cost | LOG (≤ 80 per build window), P07 |
| R9-17 | ★ | §9 | "A research request names the company by its domain in its query" | cost | LOG (research query contains the domain) |
| R9-18 | ★ | §9 | "and names the fields it asks for by the field names in §4, as the property names of its output schema." | cost | LOG (research `fields` == the six names) |

## §10 Export and import (one row per kind of state that leaves the service)

| ID | ★ | Section | Requirement (verbatim) | Kind | Probe |
|---|---|---|---|---|---|
| R10-01 | | §10 | "The service must support `GET /_test/export` and `POST /_test/import`. Like reset, these are unauthenticated control endpoints." | behaviour | P15 |
| R10-02 | | §10 | "Return 200 from export with a JSON object containing `track: \"dossier\"`, `format_version: 1` and `state` (an implementation-defined JSON object)." | format | P15 |
| R10-03 | | §10 | "The state format is opaque to the caller and must be accepted unchanged by import." | export-state | P15 |
| R10-04 | | §10 | "Import takes that entire object and atomically replaces the service's state, returning 204." | export-state | P15 |
| R10-05 | ★ | §10 | "No dependency on the source process, files, volume, port or network address is allowed." | export-state | P15 (import after reset of the same process; read) |
| R10-06 | ★ | §10 | "Import is replacement, not merge; repeating it restores the exported state without duplicating anything." | export-state | P15 (import twice → same list) |
| R10-07 | | §10 | "Invalid JSON follows §5" | error | P15 (400 malformed_request) |
| R10-08 | ★ | §10 | "missing fields, wrong track/version or an invalid state give 422 `validation_failed` without changing the destination." | error | P15 |
| R10-09 | | §10 | "These control calls have a 10-second timeout." | timing | G |
| R10-10 | ★ | §10 | "Export is an atomic, read-only snapshot; subsequent source writes do not change it." | export-state | P15 (writes after export absent after import; export makes no provider call) |
| R10-11 | ★ | §10 state | "Preserve accounts and hashed-password login" | export-state | P15 (signup user logs in after import) |
| R10-12 | ★ | §10 state | "existing bearer tokens" | export-state | P15 |
| R10-13 | ★ | §10 state | "dossiers with their ids" | export-state | P15 |
| R10-14 | ★ | §10 state | "states" | export-state | P15 (ready and failed dossiers) |
| R10-15 | ★ | §10 state | "fields, citations" | export-state | P15 (deep-equal fields) |
| R10-16 | ★ | §10 state | "`researched_at`" | export-state | P15 |
| R10-17 | ★ | §10 state | "and `spent_units`" | export-state | P15 |
| R10-18 | ★ | §10 state | "all completed idempotent request bodies and original responses." | export-state | P15 (replay → 200 original; changed body → 409) |
| R10-19 | ★ | §10 | "Identities and timestamps must not be regenerated." | export-state | P15 (user_id, dossier_id, researched_at equal) |
| R10-20 | ★ | §10 | "Import makes no provider call: imported dossiers are not researched again, and their citations remain citations served to this service." | cost | P15 (LOG unchanged) |
| R10-21 | ★ | §10 state | "Failed request keys remain reusable." | export-state | P15 |
| R10-22 | ★ | §10 | "Existing tokens and retries must remain valid after import; replacing the state with a fresh fixture does not satisfy this requirement." | export-state | P15 |
| R10-23 | ★ | §10 | "Import removes all previous destination data and credentials." | export-state | P15 (post-export user/token/dossier gone) |
| R10-24 | ★ | §10 | "Reset clears all state, including imported state." | state | P15 |
| R10-25 | ★ | §10 | "Export and import do not change the clock." | timing | P15 |
| R10-26 | | §10 | "State need not survive an abrupt container restart." | state | — (permission) |
| R10-27 | ★ | §10 | "An export taken while a build is running holds the dossier as it was before that build" | export-state | P15 |
| R10-28 | ★ | §10 | "after import, that dossier is in the state of its last completed build, or `failed` with every field `unknown` when no build had completed." | export-state | P15 (then a refresh of it works) |
| R10-29 | | §10 | "Exports may contain credentials and session tokens; handle them as private artifacts." | delivery | — (probes never write exports to disk) |

## §11 Concurrency

| ID | ★ | Section | Requirement (verbatim) | Kind | Probe |
|---|---|---|---|---|---|
| R11-01 | ★ | §11 | "Concurrent requests must produce the same results as executing them one at a time in some order." | concurrency | P04 (signup burst), P11 (bursts), P13 |
| R11-02 | ★ | §11 | "The requirements above hold at every read." | concurrency | INV on every poll during builds (P06, P10, P13) |

## Appendix A — support rules

| ID | ★ | Section | Requirement (verbatim) | Kind | Probe |
|---|---|---|---|---|---|
| RA-01 | | A | "This appendix is the whole definition of \"supports\" used in §4. The service decides support by these rules alone." | support | INV (oracle) |
| RA-02 | | A.1 | "A page's prose is split into lines at each line break, and each line into sentences." | support | oracle self-test, EV |
| RA-03 | ★ | A.1 | "A sentence ends after a `.`, `!` or `?`, together with any `\"`, `”`, `’` or `)` directly after it, when whitespace follows." | support | oracle self-test |
| RA-04 | ★ | A.1 | "A `.` that ends one of the legal-form suffixes in A.4, written as a whole word, does not end a sentence." | support | P06 (zephyr founded_year only in "Zephyr Quantum Labs Inc. was founded in 2011 …") |
| RA-05 | | A.1 | "Each sentence is taken without its surrounding whitespace; empty sentences are dropped." | support | oracle |
| RA-06 | ★ | A.1 | "An excerpt is a **single sentence** when, with every run of whitespace written as one space, this rule splits it into exactly one sentence." | support | INV |
| RA-07 | | A.2 | "1. It is a single sentence (A.1)." | support | INV |
| RA-08 | ★ | A.2 | "2. It names the company: it contains the company's normalised domain, or the company's name. The company's name is the first label of its domain with each `-` read as a space" | support | INV, P07 |
| RA-09 | | A.2 | "3. It contains a statement phrase for F (A.3)." | support | INV |
| RA-10 | ★ | A.2 | "4. It contains none of the negating phrases (A.3)." | support | P06 (reportedly / could / former traps), P07 (nordlicht "wants to") |
| RA-11 | ★ | A.2 | "5. It contains at least one value in F's format (A.4), and every value in F's format that it contains normalises to V (A.5)." | support | INV |
| RA-12 | ★ | A.2 | "The company's name, its domain and every phrase are matched without regard to case and as whole words: the characters directly before and after the match are not letters or digits." | support | oracle |
| RA-13 | | A.2 | "Phrases with a space match one space." | support | oracle |
| RA-14 | | A.2 example | "`Dana Ruiz has led Acme Robotics as chief executive since 2021.` — `ceo` `Dana Ruiz`" | support | oracle self-test |
| RA-15 | | A.2 example | "`Acme Robotics CEO: Sam Ortiz.` — `ceo` `Sam Ortiz`" | support | oracle self-test, P06 |
| RA-16 | | A.2 example | "`Acme Robotics was founded in 2014.` — `founded_year` `2014`" | support | oracle self-test |
| RA-17 | | A.2 example | "`Acme Robotics employs about 120 people.` — `headcount_range` `51-200`" | support | oracle self-test |
| RA-18 | | A.2 example | "`Acme Robotics is reportedly in talks to raise $40M.` — nothing: a negating phrase" | support | oracle self-test, P06 |
| RA-19 | | A.2 example | "`Acme Robotics opened a sales office in Porto.` — nothing: no statement phrase for `hq_city`" | support | oracle self-test |
| RA-20 | | A.3 | "`legal_name` — `legal name`, `registered name`, `registered as`, `registered company`, `legal entity`, `name of record`" | support | oracle, P06 |
| RA-21 | | A.3 | "`hq_city` — `headquartered in`, `headquarters in`, `head office in`, `based in`, `registered office in`, `registered seat in`" | support | oracle, P06, P07 |
| RA-22 | | A.3 | "`ceo` — `chief executive officer`, `chief executive`, `CEO`" | support | oracle, P06, P07 |
| RA-23 | | A.3 | "`founded_year` — `founded`, `founding`, `established`, `incorporated`" | support | oracle, P06, P07 |
| RA-24 | | A.3 | "`headcount_range` — `employs`, `employees`, `staff`, `people`, `headcount`, `workforce`" | support | oracle, P06, P07 |
| RA-25 | | A.3 | "`funding_total` — `raised`, `funding`, `invested`, `investment`" | support | oracle, P06, P07 |
| RA-26 | ★ | A.3 | "The negating phrases are: `in talks to`, `plans to`, `planning to`, `wants to`, `expects to`, `hopes to`, `aims to`, `seeking`, `could`, `would`, `might`, `reportedly`, `rumoured`, `former`, `formerly`, `will become`, `not`." | support | oracle, P06, P07 |
| RA-27 | ★ | A.4 | "A **capitalised word** is an uppercase letter followed by one or more lowercase letters, with no letter or digit directly before or after it. The letters may be of any alphabet: `Zürich` and `Müller` are capitalised words." | support | P06 (hq_city `Zürich`), P07 (`Malmö`) |
| RA-28 | | A.4 | "An **uppercase word** is two or more uppercase letters, with no letter or digit directly before or after it: `AI`, `USA`." | support | oracle |
| RA-29 | ★ | A.4 | "A **number** is written in digits, optionally with a `,` before each group of three digits and a decimal part after a `.`" | support | oracle, P07 (`3,148`) |
| RA-30 | ★ | A.4 | "Digits directly next to a letter, or joined to other digits by `,` or `.` in any other way, are not a number." | support | oracle |
| RA-31 | ★ | A.4 | "`legal_name` — The company's name or its domain (matched as in A.2), then zero or more capitalised or uppercase words each after one space, then an optional `,`, one space, and a legal-form suffix with no letter or digit directly after it. Where several such texts start at the same place, the shortest counts" | support | P06 (`Zephyr Quantum Systems GmbH`), P07 |
| RA-32 | ★ | A.4 | "`hq_city` — A place name directly after a statement phrase for `hq_city` and one space: the longest run of capitalised words joined by single spaces or by `-` that starts there, not part of a longer such run" | support | P06, P07 |
| RA-33 | ★ | A.4 | "`ceo` — A person's name: a run of two or three capitalised words joined by single spaces that is not part of a longer such run. Occurrences of the company's name and of the statement phrases for `ceo` are first taken out of the sentence and separate the words around them" | support | P06, P07 |
| RA-34 | ★ | A.4 | "`founded_year` — A number of exactly four digits, from 1800 to 2099, that is not part of an amount" | support | P06, P07 |
| RA-35 | ★ | A.4 | "`headcount_range` — A number with no decimal part, 1 or more, that is not part of an amount. Words before it, such as `about` or `roughly`, do not change it. A stated range such as `51-200 employees` holds two numbers" | support | P06 (between 60 and 150), P07 |
| RA-36 | | A.4 | "`funding_total` — An amount (below)" | support | P06, P07 |
| RA-37 | | A.4 | "The legal-form suffixes, matched exactly as written here: `Inc.`, `Corp.`, `LLC`, `LLP`, `L.P.`, `Ltd`, `Limited`, `Pty Ltd`, `plc`, `PLC`, `GmbH`, `AG`, `KG`, `SE`, `AS`, `A/S`, `ASA`, `AB`, `Oy`, `Oyj`, `B.V.`, `N.V.`, `S.A.`, `S.A.S.`, `S.L.`, `S.r.l.`, `S.p.A.`, `s.r.o.`, `a.s.`, `K.K.`." | support | oracle, P07 (`s.r.o.`, `B.V.`, `Pty Ltd`) |
| RA-38 | | A.4 | "An **amount** is written in one of these forms, matched without regard to case, with no letter or digit directly before it or after it" | support | oracle |
| RA-39 | | A.4 | "`$`, `US$` or `USD`, an optional space, a number, and optionally a scale: `k`, `m`, `mn` or `bn` directly after the number, or one space and `thousand`, `million` or `billion`." | support | oracle self-test, P06, P07 |
| RA-40 | | A.4 | "A number, optionally one space and `thousand`, `million` or `billion`, then one space and `dollars` or `US dollars`." | support | oracle self-test |
| RA-41 | ★ | A.4 | "Amounts in other currencies are not amounts." | support | P06 (zephyr "€30 million" is not funding) |
| RA-42 | | A.5 | "`legal_name`, `hq_city`, `ceo` — The text as the excerpt writes it" | support | INV |
| RA-43 | | A.5 | "`founded_year` — The number as an integer" | support | INV |
| RA-44 | | A.5 | "`headcount_range` — The range of §4 that contains the number" | support | INV |
| RA-45 | ★ | A.5 | "`funding_total` — The number times the scale (`k` and `thousand` 1,000; `m`, `mn` and `million` 1,000,000; `bn` and `billion` 1,000,000,000) in US dollars." | support | INV, P06 |
| RA-46 | ★ | A.5 | "An amount that does not come to a whole number of dollars is not a value" | support | oracle self-test |

## Planner decisions (binding interpretations)

| ID | ★ | Section | Decision (from decisions.md) | Kind | Probe |
|---|---|---|---|---|---|
| RD-01 | | D1 | "Stage 1 calls Nimble only; Tavily is never called … `TAVILY_*` variables are accepted and ignored." | cost | LOG (reported as a note, not a spec failure) |
| RD-02 | ★ | D2 | "Every build starts one Nimble research run asking for all six fields (25 units) unless the 80-unit cap forbids it; its claims are asserted only when the claim's own citation passes the Appendix A support rule" | cost | LOG, P07 (nordlicht ceo only via research) |
| RD-03 | ★ | D3 | "When several values are supported for a field, any ONE supported value is acceptable" | support | INV (probes accept any supported value) |
| RD-04 | ★ | D4 | "spent_units grows when each call is made … calls refused with an error status add 0 … reads during a build show spending so far." | cost | P10/P17 (monotonic during build, == log at end) |
| RD-05 | ★ | D5 | "The 80-unit cap is per build; spent_units is cumulative over builds" | cost | LOG, P10 |
| RD-06 | ★ | D6 | "A replay returns status 200 with the original response body (even if the first answer was 202)." | retry | P11 |
| RD-07 | | D7 | "Language: builder's choice" | delivery | — |
| RD-08 | ★ | D8 | "A research claim becomes a citation only if its excerpt is copied from text the service holds for that url … and passes Appendix A for the claimed value; otherwise dropped." | support | served-text check, P07 |
| RD-09 | ★ | D9 | "`USD12m` (no space) … Waived as spec-ambiguous … Verifier oracle and probes must not rely on `USD<digits>` without a space." | support | — (no probe or corpus page uses that form; oracle self-test has no such case) |

## Rows added by the blind re-derivation

From `factory/reviews/stage-1-blind.md`.

| ID | ★ | Section | Requirement (verbatim) | Kind | Probe |
|---|---|---|---|---|---|
| R4-50 | | §4 Fields | "Each field in a response has this shape: `{ \"value\": …, \"status\": …, \"citations\": [ { \"url\": …, \"excerpt\": …, \"provider\": … } ] }`" | format | INV |
| R4-51 | | §4 Support | "`Acme Robotics has raised $12M.` and `Acme Robotics has raised 12 million dollars.` both support a `funding_total` of `12000000`, and `Acme Robotics employs about 120 people.` supports a `headcount_range` of `51-200`." | support | oracle self-test |
| R4-52 | | §4 Fixture | fixture format `{ "now": …, "users": [ { "id", "email", "password", "display_name" } ] }` | format | P01 |
| R4-53 | | §4 Users | "Users sign up and log in (§6)." | behaviour | P04 |
| R8-43 | ★ | §8 Builds + GET | (consequence of "A failed build leaves the fields as they were" and "`state` is … the outcome of the latest build") after a failed refresh the dossier reads `state: failed` with the fields and `researched_at` of the last ready build | state | P09 |
| R8-44 | ★ | §8 GET + §9 | (consequence of "`spent_units` is the total cost (§9) of every provider call made for this dossier, by every build") spending of builds that end `failed` (timed-out calls cost their units) is included | cost | read, P09 |
| R8-45 | ★ | §8 refresh + §4 | (consequence of "Every domain the API takes, in a body or a path, is first normalised") the refresh path domain is normalised: `/dossiers/IDEM-B.test/refresh` refreshes `idem-b.test` | format | P11 |
| R8-46 | ★ | §8 list + GET | (consequence of "While a later build runs, `fields` are those of the last build that completed `ready`" and "`legal_name` is the value of the dossier's `legal_name` field") while a refresh runs the list item shows `state: building` with the last ready `legal_name` and `researched_at` | state | P10 |

## Probe index

| Probe | Covers |
|---|---|
| P00 | startup within 60 s, `/health`, no provider call from health, pre-reset clock = system time |
| P01 | reset/seed, fixture errors, stored state cleared |
| P02 | clock rules, build time = request receipt |
| P03 | unknown body fields / query params, ID length |
| P04 | signup/login rules, bearer handling, token lifetime, shared visibility, concurrent signup burst |
| P05 | domain normalisation and validation in body and path |
| P06 | verifier company `zephyr-quantum.test`: exact fields with traps (Facts header, `Inc.` sentence, negations, EUR amount, Zürich), cost window, no provider call on reads |
| P07 | evidence sweep of all 13 other corpus companies (incl. verifier company `nordlicht-optics.test`: research-only CEO, unsupported research claims) |
| P08 | company with no evidence → ready, all unknown |
| P09 | failed builds (first and later), partial failure, Tavily absent |
| P10 | refresh: reads during a build, burst of concurrent refreshes, epoch change |
| P11 | idempotency rules, replays, retried writes, bursts of identical and same-domain writes |
| P12 | list: default limit with 53 dossiers, q, order, paging, integer parameter validation |
| P13 | 50 requests in flight, invariants at every read, sum of spent_units = call-log cost |
| P14 | reset while a build runs |
| P15 | export/import: every kind of state, invalid imports, mid-build export, reset after import |
| P17 | 10 s bound with 0.8 s provider latency |
| P18 | throttled search: exactly one successful domain search |
| SERVED | every cited excerpt was served for its URL, from prose, by the named provider |
| G | no 5xx, error envelope, JSON content type, answer within timeout — on every response |

## Row count

311 rows (302 specification rows + 9 planner-decision rows), 157 marked ★.
