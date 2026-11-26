# <Project>

<README_WHAT_IT_IS>

![<README_SCREENSHOT_CAPTION>](docs/public/screenshots/<README_SCREENSHOT>.png)

## Features

### <README_AREA>

- **<README_FEATURE>** <README_FEATURE_BENEFIT>

## Quick start with Docker

You need Docker with the Compose plugin. <Project> runs from the published image
`ghcr.io/<owner>/<project>`; the server needs only two files.

1. Download `compose.yml` and the example configuration:

   ```bash
   mkdir <project> && cd <project>
   curl -fsSLO https://raw.githubusercontent.com/<owner>/<project>/main/compose.yml
   curl -fsSL https://raw.githubusercontent.com/<owner>/<project>/main/.env.example -o .env
   ```

2. Edit `.env` and set at least these values:

   | Variable | Value |
   | --- | --- |
   | `SECRET_KEY` | A random string of at least 40 characters. <Project> does not start with the placeholder. |
   | `ADMIN_PASSWORD` | Password of the first administrator (user `admin`). The example value is `administrator`: change it before the first start, or later with `set_password`. |
   | `DB_PASSWORD` | Password of the database, used only between the containers. |
   | `APP_URLS` | The address users open, e.g. `http://<project>.example.com:8080`. Keep `http://localhost:8080` to try it on your own machine. |

   Generate the random values for `SECRET_KEY` and `DB_PASSWORD` with
   `openssl rand -hex 32`.

3. Start <Project> and its database:

   ```bash
   docker compose up -d
   ```

Open <http://localhost:8080> and sign in as `admin`. Updates:
`docker compose pull && docker compose up -d`; migrations run on every start.

<!-- [DOCS] -->
For real use, put a TLS proxy in front and set `TRUSTED_PROXIES`, see
[Installation](docs/en/operations/installation.md).

## Documentation

The documentation is in [`docs/`](docs/) and inside every running instance at `/docs/`, in
English and German.

- **Operations:** [installation](docs/en/operations/installation.md),
  [all settings](docs/en/operations/configuration.md),
  [backups and updates](docs/en/operations/maintenance.md)
- **Using <Project>:** [getting started](docs/en/getting-started.md)
- **Development:** [setup, checks and architecture](docs/en/development/index.md)
<!-- [/] -->
<!-- [NO_DOCS] -->
## Operations

- **TLS:** put a TLS proxy in front and set `TRUSTED_PROXIES` to its address.
- **Settings:** every variable is explained in [`.env.example`](.env.example).
- **Backups:** the worker dumps the database nightly into the `backups` volume;
  `docker compose exec worker python manage.py backup_database` dumps right away.
<!-- [/] -->

## Contributing

<!-- [TEAM_ONLY] -->
<Project> is still in active development, so pull requests are not accepted yet; bug reports
and ideas are welcome as issues. See [CONTRIBUTING.md](CONTRIBUTING.md).
<!-- [/] -->
<!-- [EXTERNAL] -->
Bug reports, ideas and pull requests are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md).
<!-- [/] -->
To run <Project> from source:

```bash
cp .env.example .env && just setup && just migrate
just dev-backend     # second terminal: just dev-frontend → http://localhost:<DEV_PORT>
```

## License

<README_LICENSE>
