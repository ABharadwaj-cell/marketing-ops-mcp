# Contributing

Community members may review, fork, and modify the **public release for permitted noncommercial purposes** under [PolyForm Noncommercial 1.0.0](LICENSE). Existing grants made for older MIT/Perimeter releases continue to apply to copies obtained under those terms. Commercial distribution, paid hosting, resale and packaging of the current release require a separate commercial licence from the appropriate rights holder unless an express exception applies.

Pull requests are proposals; **no one can merge without authorization from the official repository maintainer**. `@ABharadwaj-cell` reviews each proposal for usefulness, originality, tests, data safety, provenance and licence compatibility. Accepted contributors may be invited to the community by separate decision; a PR alone grants no membership or commercial rights.

**Copyright and dual licensing:** submitting a PR does not automatically assign copyright or grant a right to relicense for sale. Before merging substantive copyrightable contributions, execute a separately signed Contributor Licence Agreement (CLA) sufficient to allow commercial relicensing, or a copyright assignment if truly exclusive rights in the contribution are desired. No signed agreement exists by default. [Full contribution and commercial policy](docs/COMMERCIAL_LICENSING_AND_CONTRIBUTIONS.md).

Run locally with Python 3.11+:

```sh
python -m venv .venv
. .venv/bin/activate
pip install -e '.[dev]'
pytest -q
ruff check .
pip-audit
```

Submit a focused PR with a failing example, intended behavior, tests and evidence. Use synthetic fixtures only; do not add real customer data, keys or generated outputs. Do not copy third-party code without provenance/licence review. New analytical tools must document denominators, units, assumptions, missing-data behavior and limitations. Network tools require SSRF and redirect tests.
