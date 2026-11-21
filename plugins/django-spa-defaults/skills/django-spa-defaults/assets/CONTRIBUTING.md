# Contributing to <Project>

Thanks for your interest in <Project>.

<!-- [TEAM_ONLY] -->
> [!IMPORTANT]
> <Project> is still in active development, and its structure changes often. Until that
> settles, **pull requests are not accepted**: they would mostly collide with ongoing
> work, and pull requests opened anyway are closed without review. Bug reports and ideas
> as issues are welcome. This note goes away once contributions are open.
<!-- [EXTERNAL] -->
Bug reports, ideas and pull requests are welcome. Everyone taking part follows the
[Code of Conduct](CODE_OF_CONDUCT.md).
<!-- [/] -->

## Issues

- **Bugs:** what you did, what you expected, what happened instead, and the version
  (image tag or commit). Screenshots or logs help; remove personal data first.
- **Ideas:** describe the problem you want solved before the solution, so we can find
  the fitting place in <Project> together.
- **Security issues:** do not open a public issue; report them privately through
  *Security → Report a vulnerability* on GitHub (see [SECURITY.md](SECURITY.md)).

## Pull requests

<!-- [TEAM_ONLY] -->
Not accepted for now (see above). Once they are, this is how a change gets in:
<!-- [EXTERNAL] -->
This is how a change gets in:
<!-- [/] -->

1. Discuss larger changes in an issue first.
2. Fork, branch from `main`, keep the change focused on one topic.
3. Set up the project as described in the [README](README.md).
4. Follow the conventions in [AGENTS.md](AGENTS.md): structure, services, UUID models,
   strict typing, English and German texts, no inline scripts.
5. Add or update tests; coverage must stay at or above the minimums (backend 90 %,
   frontend 90/90/85/85).
6. After model changes run `just migrations` (**DB: make migrations**), after API changes
   `just api-types` (**API: update types**), and commit the generated files.
7. Update the documentation when users or operators notice the change.
8. Run `just check` (**Check: all**) before you push; CI runs the same checks on the pull
   request.

<!-- [RELEASE_PLEASE] -->
Pull requests are squash-merged, and their title becomes the commit on `main`. Write it as a
[Conventional Commit](https://www.conventionalcommits.org/) in English: `feat: show the owner
on the detail page`, `fix: …`, `deps: …` (a dependency that reaches users), `docs: …`, `chore: …`;
`feat!:` or a `BREAKING CHANGE:` footer
for incompatible changes. Releases are made from these titles (CHANGELOG.md, version number),
so they describe the change for users.
<!-- [MANUAL_RELEASES] -->
Commit messages: an imperative summary line in English ("Show the owner on the detail
page"), a blank line, then what changed and why.
<!-- [/] -->
<!-- [EXTERNAL] -->

Sign off every commit (`git commit -s`): the `Signed-off-by` line certifies the
[Developer Certificate of Origin](https://developercertificate.org/), i.e. that you may
contribute the change under the project's license.
<!-- [/] -->

## License

<Project> is licensed under the [<LICENSE_ID>](LICENSE). By submitting a contribution
you agree that it is licensed under the same terms. Dependencies must not be under
GPL, AGPL or SSPL (checked in CI).
