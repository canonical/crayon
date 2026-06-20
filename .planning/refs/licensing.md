# dogen licensing — system of record

**Status:** binding. This file is the **complete** licensing reference for `dogen`. The source Canonical *Licensing policy* is treated as ephemeral — everything needed to make and keep `dogen` compliant is captured here. `reuse lint` enforces it in CI from commit 1.

---

## 1. Baked decisions for `dogen`

| Decision | Value | Rationale |
|---|---|---|
| Core license | **`GPL-3.0-only`** | Policy assigns GPLv3 to "everything else"; `dogen` is a CLI tool/application, not a library. `-only` (not `-or-later`) because the policy mandates "not 'v3 or later'". |
| Copyright holder | **`Canonical Ltd.`** | Canonical-owned project (epic DOCPR-2845). |
| Copyright year | **`2026`** | Policy: year = year of first publication. |
| Per-file annotation | **Full Canonical notice block** in every source file (not `REUSE.toml` bulk) | Policy mandates a per-file notice. |
| Copyright tag | `SPDX-FileCopyrightText: 2026 Canonical Ltd.` | Satisfies `reuse lint` while preserving the policy block (replaces a bare `Copyright` line). |
| License text files | `LICENSES/GPL-3.0-only.txt` (REUSE) **+** top-level `LICENSE` (policy) | Both conventions satisfied. |
| Docs/content license | **`CC-BY-SA-4.0`** | Resolved per D-44 (the first docs landed in Phase 2, plan 04). Matches the policy default (§2: new non-software → CC-BY-SA) without the commercial restriction. The earlier §3.5 CC-BY-**NC**-SA example was the policy's own inconsistency; it is reconciled to CC-BY-SA-4.0 below so §1/§2/§3.5 agree. Applied to drafted `docs/*.md` via a `.license` sidecar (no inline SPDX in published prose); `LICENSES/CC-BY-SA-4.0.txt` carries the legal text. |
| Contributions | **Canonical CLA** required; CLA-contributed files use the "License granted by Canonical Limited" notice variant | Policy contributor rules. |
| Non-default license | Would need **CEO approval** | Policy. We stay on `GPL-3.0-only`. |

---

## 2. Canonical outbound licensing rules (complete)

New open-source software is licensed by type — all "not 'or later'":

| Software type | License |
|---|---|
| Run as a service (e.g. Launchpad) | **AGPLv3** |
| Libraries | **LGPLv3** |
| Everything else | **GPLv3** ← `dogen` |
| Charms | **Apache-2.0** |

- Releasing under a **different** license requires **CEO approval**.
- Some Canonical projects are **proprietary** (e.g. Anbox Cloud, Landscape).
- **Modifications to existing OSS** are contributed under the **prevailing** license of that work.
- New **non-software** projects (graphics, sound, documentation) → **CC-BY-SA**. Documentation already under GPLv2/GPLv3 need not be relicensed.

---

## 3. Notices

Year in any copyright notice = **year of first publication** (the year the project/file was released).

### 3.1 Source-code header (the full block — use for all `dogen` `.py`/code files)

```python
# This file is part of dogen, an agentic documentation-drafting framework.
#
# SPDX-FileCopyrightText: 2026 Canonical Ltd.
# SPDX-License-Identifier: GPL-3.0-only
#
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License version 3, as published
# by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranties of MERCHANTABILITY,
# SATISFACTORY QUALITY, or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program. If not, see <http://www.gnu.org/licenses/>.
```

- **LGPL** variant: add the word **"Lesser"** before "GNU" in all three places.
- **AGPL** variant: add the word **"Affero"** in all three places.
- Include the complete license text in a file called `LICENSE` at the top of the source tree (and `LICENSES/GPL-3.0-only.txt` for REUSE).

### 3.2 Modifying an existing file

When making non-trivial modifications, add a copyright line **after** any existing copyright notice:

```
Copyright <year of first publication> Canonical Ltd.
```

### 3.3 CLA-contributed code

Code contributed under a Canonical CLA is **not** copyright Canonical, but the notice must show Canonical grants the license:

```
# This file is part of <program name + one-line description>
# Copyright <year> <Copyright holder (contributor)>
# License granted by Canonical Limited
# SPDX-License-Identifier: GPL-3.0-only
# <...GPL warranty-disclaimer paragraph, as in 3.1...>
```

(LGPL → add "Lesser"; AGPL → add "Affero".)

### 3.4 Packaging

- Document upstream copyright and license in `debian/copyright` per Debian policy.
- Packaging code is licensed under the **same** license as the software being packaged (treat it as a contribution to the work, not an aggregation).

### 3.5 Documentation header (docs license resolved — see §1)

Drafted `docs/*.md` content is licensed **`CC-BY-SA-4.0`** (D-44, reconciled with
§1/§2). The SPDX id is applied via a `.license` **sidecar** next to the page (so no
inline SPDX header pollutes the published prose or gets misparsed by `reuse lint`);
the human-readable attribution line is:

```
[name of work] © [year of first publication] by Canonical Ltd. is licensed under CC-BY-SA-4.0
```

### 3.6 Proprietary code header (not applicable to `dogen`; recorded for completeness)

```
[one line: program name + what it does] Copyright [year] Canonical Ltd. All rights reserved.
```

### 3.7 Marketing / web notices (NOT applicable to this source repo)

Marketing documents and web pages must carry Canonical's IP + company-info notice (English/French/Chinese variants exist). For completeness, the English company info: *© Canonical Limited [year]. Ubuntu, Kubuntu, Canonical and their associated logos are registered trademarks of Canonical Ltd. … Canonical Group Ltd, Registered in England and Wales, Company number 06870835, Registered Office: 5 New Street Square, London EC4A 3TW, United Kingdom. VAT Registration: GB 003 2322 47.* — Not used in code/docs of this repo.

---

## 4. Contributors

- **In-bound:** Canonical requires a contributor agreement with anyone contributing to a Canonical project. Trivial-change test: a change feasible to describe over the phone and apply correctly; multi-line patches are usually non-trivial unless they aggregate trivial changes (whitespace, typos). Contributors agree via the CLA at `ubuntu.com/legal/contributors/agreement`.
- **Out-bound:** Canonical generally contributes to upstreams where the upstream maintains the contribution. Raise a legal request if asked to sign a contribution agreement.

---

## 5. Source provenance

Distilled in full from **"Licensing policy"** — Canonical Corporate Reference Library. Type: Reference · Status: Approved · Authors: Heather Salter, Andrew Sinclair · Approved by: Teodora Mihoc · Approval date: 2023-01-01 · Review date: 2024-07-01. The raw document is **ephemeral**; this file supersedes it as the repo's system of record. (Personal email addresses from the source are omitted.)
