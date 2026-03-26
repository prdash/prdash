#!/usr/bin/env bash
# Manual fallback for updating the Homebrew formula when automated dispatch fails.
# Usage: ./scripts/update-formula.sh <version> [tap-repo-path]
#
# Example:
#   ./scripts/update-formula.sh 0.2.0 ../homebrew-prdash

set -euo pipefail

VERSION="${1:?Usage: $0 <version> [tap-repo-path]}"
TAP_REPO="${2:-../homebrew-prdash}"
FORMULA="${TAP_REPO}/Formula/prdash.rb"

if [ ! -f "$FORMULA" ]; then
  echo "Error: Formula not found at ${FORMULA}" >&2
  echo "Pass the tap repo path as the second argument." >&2
  exit 1
fi

echo "Fetching SHA256 for prdash ${VERSION} from PyPI..."

PYPI_JSON=$(curl -sf "https://pypi.org/pypi/prdash-tui/${VERSION}/json") || {
  echo "Error: Version ${VERSION} not found on PyPI" >&2
  exit 1
}

SHA256=$(echo "$PYPI_JSON" | jq -r '.urls[] | select(.packagetype=="sdist") | .digests.sha256')
URL=$(echo "$PYPI_JSON" | jq -r '.urls[] | select(.packagetype=="sdist") | .url')

if [ -z "$SHA256" ] || [ "$SHA256" = "null" ]; then
  echo "Error: Could not extract SHA256 from PyPI response" >&2
  exit 1
fi

echo "Version: ${VERSION}"
echo "URL:     ${URL}"
echo "SHA256:  ${SHA256}"
echo ""

sed -i '' "s|url \".*\"|url \"${URL}\"|" "$FORMULA"
sed -i '' "s|sha256 \".*\"|sha256 \"${SHA256}\"|" "$FORMULA"

echo "Updated ${FORMULA}"
echo ""
echo "Next steps:"
echo "  cd ${TAP_REPO}"
echo "  git add Formula/prdash.rb"
echo "  git commit -m 'Update prdash to ${VERSION}'"
echo "  git push"
