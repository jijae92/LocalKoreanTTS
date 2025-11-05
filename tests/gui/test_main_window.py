import pytest


@pytest.mark.qt
@pytest.mark.usefixtures("qapp")
def test_main_window_shows(qtbot):
    from localkoreantts.gui.main_window import MainWindow
    win = MainWindow()
    qtbot.addWidget(win)
    win.show()
    assert win.isVisible()