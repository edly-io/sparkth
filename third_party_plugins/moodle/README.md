# Sparkth publishing (`local_sparkth`)

A Moodle local plugin that adds the web service functions Sparkth needs to author courses on
your site, and declares the external service that carries them.

`local` is the Moodle plugin type, not a deployment scope — Moodle names every plugin
`<type>_<name>`, and `local` is its type for site-wide functionality that fits no more specific
one. The plugin works the same whether Sparkth runs on this server or anywhere else that can
reach it.

The plugin source is in [`sparkth/`](sparkth/). This guide covers installing it on an existing
Moodle server. Once it is installed, connect Sparkth to the site by following
[`sparkth/plugins/moodle/README.md`](../../sparkth/plugins/moodle/README.md).

## Requirements

| | |
|---|---|
| Moodle | 4.5 LTS or later |
| Access | Shell access to the Moodle server, and a site administrator account |
| Database | No schema changes — the plugin ships no `db/install.xml` |

## Step 1 — Copy the plugin into the Moodle tree

The component is `local_sparkth`, so it must live at `local/sparkth` relative to the Moodle
**webroot**, and the directory must be named exactly `sparkth`.

Two placeholders are used from here on. `<moodledir>` is the Moodle directory, the one holding
`config.php`. `<webroot>` is the directory the web server serves: up to Moodle 4.x that is
`<moodledir>` itself, and from Moodle 5.0 it is `<moodledir>/public`. Resolve yours now:

```bash
ls -d <moodledir>/public >/dev/null 2>&1 \
  && echo "webroot = <moodledir>/public" \
  || echo "webroot = <moodledir>"
```

Then copy the plugin in:

```bash
cp -r third_party_plugins/moodle/sparkth <webroot>/local/sparkth
```

Getting this wrong means the plugin is simply never discovered — Moodle reports no error.

The CLI scripts used in the next steps stay at `<moodledir>/admin/cli` on every version, outside
the webroot, so they are never web-accessible.

Set ownership so the web server can read it:

```bash
chown -R www-data:www-data <webroot>/local/sparkth
```

## Step 2 — Run the upgrade

This registers the plugin, its web service functions and the `Sparkth publishing` service.

```bash
php <moodledir>/admin/cli/upgrade.php --non-interactive
```

Or visit **Site administration → Notifications** in the browser and confirm the upgrade.

Verify it installed:

```bash
php <moodledir>/admin/cli/cfg.php --component=local_sparkth --name=version
```

The plugin should also now be listed under **Site administration → Plugins → Local plugins**.

## Step 3 — Enable web services and the REST protocol

Both are off on a stock site, and nothing works until they are on.

```bash
php <moodledir>/admin/cli/cfg.php --name=enablewebservices --set=1
php <moodledir>/admin/cli/cfg.php --name=webserviceprotocols --set=rest
```

In the UI: **Site administration → General → Advanced features → Enable web services**, then
**Site administration → Server → Web services → Manage protocols → REST protocol**.

The `Sparkth publishing` service itself needs no setup — the plugin declares it as enabled, so
it exists and is on as soon as Step 2 completes. Confirm it appears under **Site administration
→ Server → Web services → External services**.

## Installation is complete

The site can now accept Sparkth's calls, but no account is allowed to make them yet. Continue
with [`sparkth/plugins/moodle/README.md`](../../sparkth/plugins/moodle/README.md) to create the
account Sparkth will use, grant it the required permissions and issue its token.

## Upgrading the plugin

Copy the new source over `<webroot>/local/sparkth` and re-run Step 2.

Changes to the plugin's service declarations or language strings are picked up **only** when
`$plugin->version` in `version.php` increases. An installed site silently keeps the old
declarations otherwise, so confirm the version bumped before assuming a new function is
available.

## Uninstalling

Remove the plugin through **Site administration → Plugins → Plugins overview → Uninstall**,
then delete `<webroot>/local/sparkth`. Deleting the directory alone leaves the service and its
functions registered in the database.

## Troubleshooting the installation

| Symptom | Cause |
|---|---|
| Plugin absent from **Plugins → Local plugins** | Wrong install path — re-check the `<webroot>` resolution in Step 1 |
| Plugin absent, path looks right | Directory not named exactly `sparkth`, or not readable by the web server |
| Upgrade reports no plugins to install | The upgrade already ran, or `$plugin->version` did not increase |
| `Sparkth publishing` missing from External services | Step 2 did not complete, or web services are still disabled |

## Licence

GNU GPL v3 or later, matching Moodle.
