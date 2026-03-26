# GitHub Org Setup, Versioning & Homebrew Distribution

**Date**: 2026-03-25
**Status**: Approved

## Overview

Set up the prdash repo under a new GitHub organization (`prdash`), establish git-tag-driven versioning, create CI/CD pipelines, publish to PyPI, and distribute via a Homebrew tap.

## Decisions

| Decision | Choice |
|----------|--------|
| GitHub org name | `prdash` |
| License | MIT |
| Versioning | Git-tag-driven via `hatch-vcs` (semver) |
| Distribution channels | PyPI + Homebrew |
| Homebrew formula source | PyPI (virtualenv install) |
| CI/CD | GitHub Actions — PR testing + tag-triggered release |
| Homebrew auto-update | Cross-repo `repository_dispatch` with fine-grained PAT |
| Automation level | Fully automated: tag → test → PyPI → GitHub Release → tap update |

## Architecture

### Versioning Strategy

- **Source of truth**: Git tags (e.g., `v0.1.0`, `v1.2.3`)
- Replace hardcoded `version = "0.1.0"` in `pyproject.toml` with `dynamic = ["version"]`
- Add `hatch-vcs` build dependency — reads version from git tags at build time
- Add required hatch-vcs configuration sections to `pyproject.toml`:
  ```toml
  [tool.hatch.version]
  source = "vcs"

  [tool.hatch.build.hooks.vcs]
  version-file = "src/prdash/_version.py"
  ```
- `hatch-vcs` generates `src/prdash/_version.py` at build time — add it to `.gitignore`
- `importlib.metadata.version("prdash")` (already in `updater.py`) continues to work unchanged
- In dev (no tag nearby), version shows as `0.1.0.dev3+g7e3ca00`
- Semantic versioning: `MAJOR.MINOR.PATCH`

**Release flow**:
```
git tag v0.2.0
git push origin v0.2.0
→ CI tests pass
→ Publishes to PyPI as version 0.2.0
→ Creates GitHub Release "v0.2.0" with auto-generated notes
→ Dispatches to tap repo to auto-update formula
```

No files to manually edit for a release — just tag and push.

### CI/CD Workflows

#### `.github/workflows/ci.yml` — PR/push testing
- **Triggers**: push to `main`, pull requests to `main`
- **Matrix**: Python 3.12 + 3.13, ubuntu-latest
- **Steps**: checkout → `astral-sh/setup-uv` (with cache) → `uv sync` → `uv run pytest` → (optionally `uv run mypy src/`)

#### `.github/workflows/release.yml` — Tag-triggered release
- **Trigger**: push tags matching `v*`
- **Jobs** (sequential):
  1. **test** — same matrix as CI, must pass before publish
  2. **publish-pypi** — `hatch build` → upload via PyPI Trusted Publisher (no API tokens)
  3. **github-release** — creates GitHub Release with auto-generated notes
  4. **update-homebrew** — dispatches `repository_dispatch` to `prdash/homebrew-prdash` with version + SHA256
- **Environment**: `release` (required for PyPI Trusted Publisher)

### Homebrew Tap

#### Tap repo: `prdash/homebrew-prdash`
- Install command: `brew tap prdash/prdash && brew install prdash`
- Contains `Formula/prdash.rb` and `.github/workflows/update-formula.yml`

#### Formula: `Formula/prdash.rb`

Since this is a personal tap (not homebrew-core), we use `pip install` with full dependency resolution rather than maintaining 20-30+ explicit `resource` blocks for every transitive dependency (textual, httpx, pydantic, and all their sub-dependencies). The `virtualenv_install_with_resources` method requires explicit resource blocks for each dependency and would fail without them.

```ruby
class Prdash < Formula
  include Language::Python::Virtualenv

  desc "Terminal dashboard for monitoring GitHub PRs requiring your attention"
  homepage "https://github.com/prdash/prdash"
  url "https://files.pythonhosted.org/packages/source/p/prdash/prdash-0.1.0.tar.gz"
  sha256 "<sha256-of-initial-release>"
  license "MIT"

  depends_on "python@3.12"

  def install
    virtualenv_create(libexec, "python3.12")
    system libexec/"bin/pip", "install", "prdash==#{version}"
    bin.install_symlink Dir[libexec/"bin/prdash"]
  end

  test do
    assert_match version.to_s, shell_output("#{bin}/prdash --version")
  end
end
```

#### Auto-update workflow: `.github/workflows/update-formula.yml` (in tap repo)
- Triggered by `repository_dispatch` event from main repo
- Receives version string from dispatch payload
- Fetches SHA256 from PyPI JSON API:
  ```bash
  sha256=$(curl -sL "https://pypi.org/pypi/prdash/${VERSION}/json" \
    | jq -r '.urls[] | select(.packagetype=="sdist") | .digests.sha256')
  ```
- Updates `Formula/prdash.rb` with new version + SHA256 → commits and pushes

### Updater Changes

Update `src/prdash/updater.py` to detect Homebrew installs:
- Check if `sys.prefix` is under a Homebrew Cellar path
- If Homebrew-installed, `prdash --update` prints: "Installed via Homebrew. Run: `brew upgrade prdash`"

## Manual Steps (User Must Do)

### Before agent implementation
1. **Create GitHub org** `prdash` at https://github.com/account/organizations/new

### After agent implementation (code committed)
2. **Create main repo on GitHub**:
   ```bash
   gh repo create prdash/prdash --public --source=. --remote=origin --push
   ```
3. **Create tap repo on GitHub**:
   ```bash
   gh repo create prdash/homebrew-prdash --public --clone
   ```
   Then copy the formula + workflow files and push.

4. **Set up PyPI Trusted Publisher**:
   - Go to https://pypi.org/manage/account/publishing/
   - Add pending publisher: owner=`prdash`, repo=`prdash`, workflow=`release.yml`, environment=`release`

5. **Create fine-grained PAT** for cross-repo dispatch:
   - https://github.com/settings/tokens → Fine-grained tokens
   - Scope to `prdash/homebrew-prdash` repo, permissions: Contents (read+write) + Actions (read+write)
   - Add as repo secret `HOMEBREW_TAP_TOKEN` in `prdash/prdash` settings
   - **Test the token**: verify `repository_dispatch` works before relying on it in CI

6. **Tag and push first release**:
   ```bash
   git tag v0.1.0
   git push origin v0.1.0
   ```

## Automated by Agent (Code Changes)

### Files to create
| File | Purpose |
|------|---------|
| `LICENSE` | MIT license file |
| `.github/workflows/ci.yml` | PR/push test workflow |
| `.github/workflows/release.yml` | Tag-triggered release pipeline |
| `homebrew/Formula/prdash.rb` | Homebrew formula (to be copied to tap repo) |
| `homebrew/.github/workflows/update-formula.yml` | Tap auto-update workflow (to be copied to tap repo) |
| `scripts/update-formula.sh` | Manual fallback for updating Homebrew formula (used in failure recovery) |

### Files to modify
| File | Changes |
|------|---------|
| `pyproject.toml` | Switch to `hatch-vcs`, add `[tool.hatch.version]` + `[tool.hatch.build.hooks.vcs]`, add metadata (homepage, repo, license, authors) |
| `src/prdash/updater.py` | Detect Homebrew installs, suggest `brew upgrade` |
| `.gitignore` | Add `src/prdash/_version.py` (generated by hatch-vcs at build time) |
| `README.md` | Add Homebrew install instructions, update install section |
| `WORK_TRACKER.md` | Update T32 and T33 status (this spec covers both) |

## Release Failure Recovery

Since the release pipeline is sequential (test → PyPI → GitHub Release → tap dispatch), failures can leave partial state:

| Failure point | State | Recovery |
|---------------|-------|----------|
| Tests fail | Nothing published | Fix, delete tag, re-tag, push |
| PyPI publish fails | Tag exists, nothing published | Delete tag, fix issue, re-tag, push |
| PyPI succeeds, GH Release fails | Package on PyPI | Manually create GitHub Release, then trigger tap update |
| Tap dispatch fails | Package on PyPI + GH Release | Manually update formula: run `scripts/update-formula.sh <version>` |

**Important**: Deleting and re-pushing a git tag is the escape hatch for pre-PyPI failures. Once a version is on PyPI, that version number is permanently consumed — you must bump to a new version.

## Security Notes

- All workflow actions should be pinned to commit SHAs (not tags) to prevent supply-chain attacks
- The `HOMEBREW_TAP_TOKEN` PAT should be scoped as narrowly as possible (single repo, minimal permissions)
- PyPI Trusted Publisher eliminates the need for long-lived API tokens

## Acceptance Criteria

- [ ] `hatch-vcs` reads version from git tags; `prdash --version` shows correct version
- [ ] CI workflow runs pytest on push/PR with Python 3.12 + 3.13 matrix
- [ ] Release workflow triggers on `v*` tags: tests → PyPI → GitHub Release → tap dispatch
- [ ] Homebrew formula installs `prdash` into a working state via `brew install`
- [ ] `prdash --update` detects Homebrew install and suggests `brew upgrade prdash`
- [ ] README documents all install methods including Homebrew
- [ ] Release process requires zero file edits — just `git tag` + `git push`
