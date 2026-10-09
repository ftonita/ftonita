# Releasing

1. Update `CHANGELOG.md` (move `Unreleased` items under a new version) and `__version__` in
   `src/pipeline_platform/__init__.py`.
2. `python scripts/update_golden.py` if generated output changed intentionally; review the diff.
3. `pytest` and `ruff check .` must be green.
4. Tag and publish:
   ```bash
   git tag -a v1.0.1 -m "v1.0.1" && git push origin v1.0.1
   git tag -fa v1 -m "v1" && git push -f origin v1     # moving major tag
   docker build -t registry.example.com/platform/pipeline-platform:v1.0.1 . && docker push ...
   docker tag ... :v1 && docker push ...                # same moving-tag rule for the image
   ```
5. Consumers on `ref: v1` pick the change up on their next pipeline. A breaking change means `v2`, a new
   `schema/platform.v2.schema.json` and `version: 2` in `.platform.yml`; `v1` keeps working unchanged.

**Compatibility promise for `v1.x`:** valid `.platform.yml` files stay valid; generated job names
(`test`, `build`, `trivy`, `deploy:<env>`, ...) and the variables `IMAGE`, `IMAGE_TAG`,
`IMAGE_REPOSITORY` do not change.
