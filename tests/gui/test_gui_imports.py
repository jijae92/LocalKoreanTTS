def test_gui_modules_importable():
    import localkoreantts.gui.app as app
    import localkoreantts.gui.main_window as mw
    assert hasattr(app, "main")
    assert hasattr(mw, "MainWindow")
