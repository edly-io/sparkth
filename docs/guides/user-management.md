# User management

Users are created and managed from the command line. This is the primary path when
frontend registration is disabled (see [`REGISTRATION_ENABLED`](../reference/configuration.md#registration_enabled)).

## Create a user

```bash
make create-user -- --username john --email john@example.com --name "John Doe"
# Using short flags
make create-user -- -u john -e john@example.com -n "John Doe"
```

If a password is not provided via flag, you'll be prompted to enter it securely.

Create an admin user — grants the global `admin` role (run `make migrations` first so the
role is seeded):

```bash
make create-user -- --username admin --email admin@example.com --name "Admin User" --admin
```

Provide the password directly:

```bash
make create-user -- -u john -e john@example.com -n "John Doe" --password "SecurePass123"
```

Options:

- `--username, -u`: Username (required)
- `--email, -e`: Email address (required)
- `--name, -n`: Full name (optional, defaults to the username)
- `--password, -p`: Password (optional, will prompt if not provided)
- `--email-verified`: mark the user's email as already verified (optional, default: false)
- `--admin` (alias `--superuser`): also grant the user the global `admin` role (optional,
  default: false). The `admin` role must already be seeded (via `make migrations`), or the
  command exits without creating the user. See the [permissions guide](permissions.md) for
  what the `admin` role grants.

## Reset a password

The user is given as a positional username **or** email:

```bash
make reset-password -- john
# Provide the password directly
make reset-password -- john --new-password "NewSecurePass123"
make reset-password -- john -p "NewSecurePass123"
```

Options:

- `identifier`: Username or email of the user (required, positional)
- `--new-password, -p`: New password (optional, will prompt if not provided)
