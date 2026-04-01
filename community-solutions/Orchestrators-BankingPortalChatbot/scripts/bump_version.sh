#!/bin/bash
# Usage: ./bump_version.sh 0.8.0
set -e

if [ -z "$1" ]; then
    echo "Usage: $0 <new_version>"
    echo "Example: $0 0.8.0"
    exit 1
fi

NEW_VERSION="$1"
DIR="$(cd "$(dirname "$0")" && pwd)"

echo "Bumping version to $NEW_VERSION..."

# Update VERSION file
echo "$NEW_VERSION" > "$DIR/VERSION"

# Update pyproject.toml
sed -i "s/^version = \".*\"/version = \"$NEW_VERSION\"/" "$DIR/pyproject.toml"

echo "Updated files:"
echo "  VERSION: $(cat "$DIR/VERSION")"
grep -n "^version" "$DIR/pyproject.toml"
echo ""
echo "Don't forget to:"
echo "  1. Add a new section in CHANGELOG.md for [$NEW_VERSION]"
echo "  2. git add -A && git commit -m 'Bump version to $NEW_VERSION'"
echo "  3. git tag v$NEW_VERSION"
