class SettingsManager:
    def __init__(self):
        self.settings = {
            'text_color': "#FFFFFF",
            'bg_color': "#000000",
            'font_size': 24,
            'text_border': True,
            'text_shadow': False,
            'batch_size': 50,
            'speed_factor': 1.0,
            'margin': 20,
        }

    def update_settings(self, new_settings):
        self.settings.update(new_settings)

    def get_settings(self):
        return self.settings