#!/bin/bash

echo "=============================="
echo " IOT DASHBOARD AUTO COMMIT"
echo "=============================="

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR" || exit 1

echo ""
echo "Adding files..."
git add .

if git diff --cached --quiet; then
    echo "No changes to commit."
else
    TS=$(date "+%Y-%m-%d %H:%M:%S")

    echo "Commit: $TS"

    git commit -m "auto commit $TS"

    echo "Pushing to GitHub..."
    git push origin main
fi


# ----------------------------------------
# SUGGEST NEXT TAG
# ----------------------------------------

LAST_TAG=$(git tag --list "v*.*.*" --sort=-v:refname | head -n 1)

if [ -z "$LAST_TAG" ]; then
    SUGGESTED="v1.0.0"
else
    VER=${LAST_TAG#v}

    IFS='.' read -r MAJOR MINOR PATCH <<< "$VER"

    PATCH=$((PATCH + 1))

    SUGGESTED="v${MAJOR}.${MINOR}.${PATCH}"
fi

echo ""
echo "Last tag: ${LAST_TAG:-none}"

read -p "Create release tag? [${SUGGESTED}] (ENTER=skip): " TAG

if [ -z "$TAG" ]; then
    echo "No tag created."
    exit
fi

if [[ "$TAG" != v* ]]; then
    TAG="v$TAG"
fi

echo "Creating tag $TAG"

git tag -a "$TAG" -m "release $TAG"

git push origin "$TAG"

echo "Tag pushed."