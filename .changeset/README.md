# Changesets

Every pull request that changes what a user can see, install or run needs a changeset. Create one
with `pnpm changeset`, pick the bump, and describe the change in terms of what the user gets — the
text is copied verbatim into `CHANGELOG.md` and read by people who never see the diff.

A pull request with no user-visible effect — a test, a refactor, CI plumbing — needs no changeset.

Merging a changeset to `main` does not release anything. It opens or updates a "Version Packages"
pull request that collects the pending changesets; the release happens when that pull request is
merged. See the release section of `CONTRIBUTING.md`.

`privatePackages` is set because the app is `"private": true`, which Changesets otherwise skips
entirely: without it `changeset version` would succeed and bump nothing.
