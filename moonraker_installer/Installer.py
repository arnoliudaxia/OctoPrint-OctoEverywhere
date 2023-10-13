import os
import sys
import traceback

from .Linker import Linker
from .Logging import Logger
from .Service import Service
from .Context import Context
from .Discovery import Discovery
from .DiscoveryObserver import DiscoveryObserver
from .Configure import Configure
from .Updater import Updater

class Installer:

    def Run(self):
        try:
            # Any error during the process will be thrown, which will be printed here, and exit the installer.
            self._RunInternal()
        except Exception as e:
            tb = traceback.format_exc()
            Logger.Blank()
            Logger.Blank()
            Logger.Error("Installer failed - "+str(e))
            Logger.Blank()
            Logger.Blank()
            Logger.Error("Stack Trace:")
            Logger.Error(str(tb))
            Logger.Blank()
            Logger.Blank()
            Logger.Header("Please contact our support team directly at support@octoeverywhere.com so we can help you fix this issue!")
            Logger.Blank()
            Logger.Blank()


    def _RunInternal(self):
        # Next, we must handle the program args.
        # The installer script passes a json object to us, which contains all of the args.
        # But it might not be the first arg.
        argObjectStr = self.GetArgumentObjectStr()
        if argObjectStr is None:
            raise Exception("Failed to find cmd line json arg")

        # Parse and validate the args.
        context = Context.LoadFromArgString(argObjectStr)

        # As soon as we have the user home make the log file.
        Logger.InitFile(context.UserHomePath)

        # Validate we have the required args, but not the moonraker values yet, since they are optional.
        Logger.Debug("Validating args")
        # All generation 1 vars must exist and be valid.
        context.Validate(1)

        # Parse the original CmdLineArgs
        Logger.Debug("Parsing script cmd line args.")
        context.ParseCmdLineArgs()

        if context.Debug:
            # Print this again, since it might be useful.
            Logger.Debug("Found config: "+argObjectStr)

        if context.ShowHelp:
            # If we should show help, do it now and return.
            self.PrintHelp()
            return

        #
        # Ready to go!

        # First, ensure we are launched as root.
        # pylint: disable=no-member # Linux only
        if os.geteuid() != 0:
            if context.Debug:
                Logger.Warn("Not running as root, but ignoring since we are in debug.")
            else:
                raise Exception("Script not ran as root.")

        # Before discover, check if we are in update mode.
        # In update mode we just enumerate all known local plugins and companions, update them, and then we are done.
        if context.IsUpdateMode:
            update = Updater()
            update.DoUpdate(context)
            return

        # Next step is to discover and fill out the moonraker config file path and service file name.
        # If we are doing an observer setup, we need the user to help us input the details to the external moonraker IP.
        # This is the hardest part of the setup, because it's highly dependent on the system and different moonraker setups.
        if context.IsObserverSetup:
            discovery = DiscoveryObserver()
            discovery.ObserverDiscovery(context)
        else:
            discovery = Discovery()
            discovery.FindTargetMoonrakerFiles(context)

        # Validate the response.
        # All generation 2 values must be set and valid.
        if context is None:
            raise Exception("Discovery returned an invalid context.")
        context.Validate(2)

        # Next, based on the vars generated by discovery, complete the configuration of the context.
        configure = Configure()
        configure.Run(context)

        # After configuration, gen 3 should be fully valid.
        context.Validate(3)

        # Before we start the service, check if the secrets config file already exists and if a printer id already exists.
        # This will indicate if this is a fresh install or not.
        context.ExistingPrinterId = Linker.GetPrinterIdFromServiceSecretsConfigFile(context)

        # Final validation
        context.Validate(4)

        # We are fully configured, create the service file and it's dependent files.
        service = Service()
        service.Install(context)

        # Add our auto update logic.
        updater = Updater()
        # If this is an observer, put the update script in the users root, so it's easy to find.
        if context.IsObserverSetup:
            updater.PlaceUpdateScriptInRoot(context)
        # Also setup our cron updater if we can, so that the plugin will auto update.
        updater.EnsureCronUpdateJob(context)

        # The service is ready! Now do the account linking process.
        linker = Linker()
        linker.Run(context)

        # Success!
        Logger.Blank()
        Logger.Blank()
        Logger.Blank()
        Logger.Purple("        ~~~ OctoEverywhere For Klipper Setup Complete ~~~    ")
        Logger.Warn(  "  You Can Access Your Printer Anytime From OctoEverywhere.com")
        Logger.Header("                   Welcome To Our Community                  ")
        Logger.Error( "                            <3                               ")
        Logger.Blank()
        Logger.Blank()


    def GetArgumentObjectStr(self) -> str:
        for arg in sys.argv:
            if len(arg) > 0 and arg[0] == '{':
                return arg
        return None


    def PrintHelp(self):
        Logger.Blank()
        Logger.Blank()
        Logger.Blank()
        Logger.Blank()
        Logger.Header("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
        Logger.Header("    OctoEverywhere For Klipper      ")
        Logger.Header("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
        Logger.Blank()
        Logger.Info("This installer script is used for installing the OctoEverywhere plugin on Klipper/Moonraker/Mainsail/Fluidd setups. It is NOT used for OctoPrint setups.")
        Logger.Info("If you want to install OctoEverywhere for OctoPrint, use the plugin manager in OctoPrint's settings to install the plugin.")
        Logger.Blank()
        Logger.Warn("Command line format:")
        Logger.Info("  <moonraker config file path> <moonraker service file path> -other -args")
        Logger.Blank()
        Logger.Warn("Argument details:")
        Logger.Info("  <moonraker config file path>  - optional - If supplied, the install will target this moonraker setup without asking or searching for others")
        Logger.Info("  <moonraker service name> - optional - If supplied, the install will target this moonraker service file without searching.")
        Logger.Info("       Used when multiple moonraker instances are ran on the same device. The service name is used to find the unique moonraker identifier. OctoEverywhere will follow the same naming convention. Typically the file name is something like `moonraker-1.service` or `moonraker-somename.service`")
        Logger.Info("  -observer - optional flag - If passed, the plugin is setup as an observer, which is a plugin not running on the same device as moonraker. This is useful for built-in printer hardware where OctoEverywhere can't run, like the Sonic Pad or K1.")
        Logger.Blank()
        Logger.Warn("Other Optional Args:")
        Logger.Info("  -help            - Shows this message.")
        Logger.Info("  -noatuoselect    - Disables auto selecting a moonraker instance, allowing the user to always choose.")
        Logger.Info("  -debug           - Enable debug logging to the console.")
        Logger.Info("  -skipsudoactions - Skips sudo required actions. This is useful for debugging, but will make the install not fully work.")
        Logger.Blank()
        Logger.Info("If you need help, contact our support team at support@octoeverywhere.com")
        Logger.Blank()
        Logger.Blank()
