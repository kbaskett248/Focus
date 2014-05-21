import os

import sublime

from .RingCompleter import RingCompleter

try:
    import sublimelogging
    logger = sublimelogging.getLogger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

class SystemRingCompleter(RingCompleter):
    """Loads completions from a View."""

    EmptyReturn = ([], sublime.INHIBIT_WORD_COMPLETIONS | sublime.INHIBIT_EXPLICIT_COMPLETIONS)

    CompletionTypes = [RingCompleter.CT_SYSTEM]

    LoadAsync = False

    SystemVariables = ("AboutBoxProgram",
                    "AccessLocalData",
                    "ANPTimeServer",
                    "AppCallbackExternalSub",
                    "AuditCode",
                    "AuditExternalSub",
                    "AuditProcessOff",
                    "AuditReadOff",
                    "AuditReadOn",
                    "AuditWriteOff",
                    "AuditWriteOn",
                    "BaseWindowSize",
                    "Client",
                    "ClientType",
                    "CodeUpdateRequired",
                    "CurrentProgram",
                    "DataDefProgram",
                    "DisableClientMessaging",
                    "DisableDataCache",
                    "DisableObjectLogging",
                    "DisableTransactionProcessing",
                    "DisconnectedSuffix",
                    "EmailProgram",
                    "EmulatedUser",
                    "ErrorProcess",
                    "Font",
                    "GlobalScreenStylesProgram",
                    "GlobalWebStylesProgram",
                    "HCIS",
                    "HelpProgram",
                    "MastScanServer",
                    "MaximizeExtraLargeWindow",
                    "MeditorLinkExternalSub",
                    "MeditorPrintExternalSub",
                    "OverrideClientName",
                    "Palette",
                    "PrintPrefProgram",
                    "PrintScrnProgram",
                    "ProcessControlledBy",
                    "ProcessGroup",
                    "ProcessIcon",
                    "ProcessMessage",
                    "PropertiesBoxProgram",
                    "ReferencesProgram",
                    "ReservedFilenameConversion",
                    "RetainErrorTrap",
                    "RingIndexType",
                    "RingSystemOIDBucketing",
                    "RootAccessViolationExternalSub",
                    "ServerCurrentRecordFilteringDisabled",
                    "SessionTempEncryptionOff",
                    "ShiftF4Program",
                    "ShowScreenDelayTimes",
                    "SignonUserMnemonic",
                    "SignonUserName",
                    "SpyExternalSub",
                    "SuppressHoverPointer",
                    "SuspendProgram",
                    "TimeInProgram",
                    "Timeout",
                    "TimeoutProgram",
                    "UnvIndexType",
                    "UnvSystemOIDBucketing",
                    "UserMnemonic",
                    "UserName",
                    "ViewOnlyMode",
                    "WebValidationProgram",
                    "WindowTitleSuffixExternalSub")

    @RingCompleter.api_call
    def load_completions(self, **kwargs):
        """Loads alias completions from the ring."""
        self.completions = set([(v, ) for v in SystemRingCompleter.SystemVariables])
        