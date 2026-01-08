class PinchScrollState:
    def __init__(self):
        self.active = False
        self.start_x = 0.0
        self.start_y = 0.0

    def start(self, x, y):
        self.active = True
        self.start_x = float(x)
        self.start_y = float(y)

    def stop(self):
        self.active = False

    def delta(self, x, y):
        return float(x) - self.start_x, float(y) - self.start_y