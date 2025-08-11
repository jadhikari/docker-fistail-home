from django.apps import AppConfig


class TargetsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'targets'
    verbose_name = 'Target Management'

    def ready(self):
        """Import signals when app is ready"""
        try:
            import targets.signals  # noqa F401
        except ImportError:
            pass