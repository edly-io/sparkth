#!/usr/bin/env python3
"""
Sparkth CLI - Command line interface for the Sparkth project
"""
import click


@click.group()
@click.version_option(version="0.1.0")
def cli():
    """Sparkth command line interface"""
    pass


@cli.group()
def plugins():
    """Plugin management commands"""
    pass


@plugins.command('list')
def list_plugins():
    """List all installed and enabled plugins"""
    from app.plugins import iter_installed, discover_plugins
    from app.plugins.manager import get_manager
    
    # Discover plugins first
    discover_plugins()
    
    manager = get_manager()
    installed = list(iter_installed())
    enabled = manager.get_enabled_plugins()
    
    click.echo("Installed plugins:")
    for plugin in installed:
        status = "✓ enabled" if plugin in enabled else "  disabled"
        click.echo(f"  {status} - {plugin}")
    
    if not installed:
        click.echo("  (none)")


@plugins.command('enable')
@click.argument('plugin_name')
def enable_plugin(plugin_name):
    """Enable a plugin"""
    from app.plugins.manager import get_manager
    from app.plugins import is_installed, discover_plugins
    
    discover_plugins()
    
    if not is_installed(plugin_name):
        click.echo(f"Error: Plugin '{plugin_name}' is not installed", err=True)
        return
    
    manager = get_manager()
    manager.enable_plugin(plugin_name)
    click.echo(f"Plugin '{plugin_name}' enabled successfully")


@plugins.command('disable')
@click.argument('plugin_name')
def disable_plugin(plugin_name):
    """Disable a plugin"""
    from app.plugins.manager import get_manager
    
    manager = get_manager()
    manager.disable_plugin(plugin_name)
    click.echo(f"Plugin '{plugin_name}' disabled successfully")


@plugins.command('info')
@click.argument('plugin_name', required=False)
def plugin_info(plugin_name):
    """Show information about plugins"""
    from app.plugins import iter_info, discover_plugins
    
    discover_plugins()
    
    info_list = list(iter_info())
    
    if plugin_name:
        # Show info for specific plugin
        for name, info in info_list:
            if name == plugin_name:
                click.echo(f"Plugin: {name}")
                click.echo(f"Info: {info}")
                return
        click.echo(f"Plugin '{plugin_name}' not found", err=True)
    else:
        # Show all plugins
        click.echo("Plugin Information:")
        for name, info in info_list:
            click.echo(f"  {name}: {info}")


@plugins.group('migrate')
def migrate():
    """Database migration commands for plugins"""
    pass


@migrate.command('create')
@click.argument('plugin_name')
@click.argument('message')
def create_migration(plugin_name, message):
    """Create a new migration for a plugin
    
    Example: sparkth plugins migrate create my_plugin "add tasks table"
    """
    from app.plugins.migrations import PluginMigrationManager
    from app.plugins import discover_plugins, load
    
    # Discover and load plugin to register models
    discover_plugins()
    load(plugin_name)
    
    manager = PluginMigrationManager(plugin_name)
    
    # Check if plugin has models
    models = manager.get_plugin_models(plugin_name)
    if not models:
        click.echo(f"Warning: No models found for plugin '{plugin_name}'", err=True)
        click.echo("Make sure your plugin registers models with Filters.SQLMODEL_MODELS")
        return
    
    click.echo(f"Found {len(models)} model(s) for {plugin_name}")
    for model in models:
        click.echo(f"  - {model.__name__}")
    
    click.echo(f"\nGenerating migration...")
    migration_file = manager.create_migration(message, plugin_name)
    
    if migration_file:
        click.echo(f"✓ Migration created: {migration_file}")
    else:
        click.echo("✗ Failed to create migration", err=True)


@migrate.command('apply')
@click.option('--target', default='head', help='Target revision (default: head)')
def apply_migrations(target):
    """Apply pending migrations"""
    from app.plugins.migrations import PluginMigrationManager
    
    manager = PluginMigrationManager()
    
    click.echo(f"Applying migrations to {target}...")
    try:
        manager.apply_migrations(target)
        click.echo("✓ Migrations applied successfully")
    except Exception as e:
        click.echo(f"✗ Error applying migrations: {e}", err=True)


@migrate.command('rollback')
@click.option('--steps', default='-1', help='Number of steps to rollback (default: -1)')
def rollback_migrations(steps):
    """Rollback migrations"""
    from app.plugins.migrations import PluginMigrationManager
    
    manager = PluginMigrationManager()
    
    click.echo(f"Rolling back {abs(int(steps))} step(s)...")
    try:
        manager.rollback_migrations(steps)
        click.echo("✓ Migrations rolled back successfully")
    except Exception as e:
        click.echo(f"✗ Error rolling back migrations: {e}", err=True)


@migrate.command('models')
@click.argument('plugin_name', required=False)
def list_models(plugin_name):
    """List models for a plugin or all plugins"""
    from app.plugins.migrations import PluginMigrationManager
    from app.plugins import discover_plugins, iter_loaded
    
    # Discover and load plugins
    discover_plugins()
    
    if plugin_name:
        from app.plugins import load
        load(plugin_name)
        plugins_to_check = [plugin_name]
    else:
        # Load all enabled plugins
        for p in iter_loaded():
            pass
        plugins_to_check = [None]  # None means all plugins
    
    for plugin in plugins_to_check:
        manager = PluginMigrationManager(plugin)
        models = manager.list_plugin_models(plugin)
        
        if plugin:
            click.echo(f"\nModels for plugin '{plugin}':")
        else:
            click.echo("\nAll plugin models:")
        
        if models:
            for model in models:
                click.echo(f"  - {model['name']}")
                click.echo(f"    Table: {model['table']}")
                click.echo(f"    Module: {model['module']}")
        else:
            click.echo("  (no models found)")


if __name__ == "__main__":
    cli()
