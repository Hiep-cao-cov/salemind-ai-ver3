from utils.db import get_manager_analytics


def load_dashboard_data() -> dict:
    return get_manager_analytics()
