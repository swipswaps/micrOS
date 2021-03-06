"""
Module is responsible for invoke micrOS or recovery webrepl mode

Designed by Marcell Ban aka BxNxM
"""
#################################################################
#                    IMPORTS & START micrOS                     #
#################################################################
try:
    # Simulator debug requirement...
    import traceback
except:
    traceback = None


def __is_micrOS():
    """
    Recovery mode for OTA update in case of connection/transfer failure
        .if_mode can have 2 possible values: webrepl or micros (strings)
    If the system is healthy / OTA update was successful
        .if_mode should contain: micros [return True]
    In other cases .if_mode should contain: webrepl [return False]

    It will force the system in bootup time to start
    webrepl (update) or micrOS (default)

    return
        True -> micrOS
        False -> webrepl
    """

    try:
        with open('.if_mode', 'r') as f:
            if_mode = f.read().strip().lower()
    except Exception:
        # start micrOS
        print("[loader][if_mode:True] .if_mode file not exists -> micros interface")
        return True

    if if_mode == 'micros':
        # start micrOS
        print("[loader][if_mode:True] .if_mode:{} -> micros interface".format(if_mode))
        return True
    # start webrepl
    print("[loader][if_mode:False] .if_mode:{} -> webrepl interface".format(if_mode))
    print("[loader][recovery mode] - manually selected in .if_mode file")
    return False


def __recovery_mode():
    # Recovery mode (webrepl) - dependencies: Network, ConfigHandler
    from Network import auto_network_configuration
    try:
        from ConfigHandler import cfgget
    except:
        cfgget = None
    # Set up network
    auto_network_configuration()
    # Start webrepl
    import webrepl
    webrepl.start(password = 'ADmin123' if cfgget is None else cfgget('appwd'))


def __auto_restart_event():
    """
    Poll .if_mode value main loop in case of webrepl (background) mode:
        Events for execute reboot:
            - value: webrepl    [wait for update -> updater writes webrepl value under update]
            - value: micros     [update was successful - reboot is necessary]
    :return:
    """
    from time import sleep
    trigger_is_active = False
    wait_for_update_start_timeoutcnt = 7
    # Wait after webrepl started for possible ota updates (~2*7= 14sec)
    while wait_for_update_start_timeoutcnt > 0:
        # Wait for micros turns to  webrepl until timeout
        if __is_micrOS():
            # micrOS mode
            print("[loader][ota auto-rebooter][micros][{}] Wait for OTA update possible start".format(wait_for_update_start_timeoutcnt))
            wait_for_update_start_timeoutcnt -= 1
        else:
            print("[loader][ota auto-rebooter][webrepl/None][{}] Update status: InProgress".format(wait_for_update_start_timeoutcnt))
            # Set trigger  - if_mode changed to webrepl - ota update started - trigger wait
            trigger_is_active = True
        # Restart if trigger was activated
        if trigger_is_active and __is_micrOS():
            print("[loader][ota auto-rebooter][micros][trigger: True] OTA was finished - reboot")
            from machine import reset
            reset()
        sleep(2)


def main():
    if __is_micrOS():
        # Main mode
        try:
            print("[loader][main mode] Start micrOS (default)")
            from micrOS import micrOS
            micrOS()
        except Exception as e:
            if traceback is not None: traceback.print_exc()
            # Handle micrOS system crash (never happened...but) -> webrepl mode default pwd: ADmin123
            print("[loader][main mode] micrOS start failed: {}".format(e))
            print("[loader][main mode] -> [recovery mode]")
    # Recovery aka webrepl mode
    __recovery_mode()
    __auto_restart_event()


if __name__ == '__main__':
    main()

