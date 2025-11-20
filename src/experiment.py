from datetime import datetime, timezone
from pathlib import Path
import threading
import logging
import time
import json
import copy

from utils import *
from cumucore import Cumucore
from qosium import Qosium
from ai import Ai
from osm import Osm
from ovs import Ovs

logger = logging.getLogger("experiment")

currentDir = Path(__file__).parent
mainConfFile = currentDir.parent / "conf" / "config.json"

class Experiment:
    """Main class that manages experiment lifecycles."""

    # The state identifiers of experiment
    STATE_READY = "ready"
    STATE_INITIALIZE = "initialize"
    STATE_EXECUTE = "execute"
    STATE_CLEANUP = "cleanup"
    STATE_DONE = "done"
    STATE_ERROR = "error"

    def __init__(self):
        """
        Initialize an Experiment instance.
        """
        self.runningLock = threading.Lock()
        self.statusLock = threading.Lock()
        self._thread = None
        self._stop_event = threading.Event()
        self.id = None
        self.state = self.STATE_READY
        self.message = None
        self.log = ""
        self.nst = None
        self.startTime = None
        self.stopTime = None
        self.slices = []
        self.apps = []

        # Load contents from the main configuration file
        self.config = json.loads(readFileContents(mainConfFile))

        # Create all the sub-modules
        self.qosium = Qosium(self.config)
        self.ai = Ai(self.config)
        self.cumucore = Cumucore(self.config)
        self.osm = Osm(self.config)
        self.ovs = Ovs(self.config)

    def run(self):
        """
        The run function executed within the experiment thread.
        """
        try:
            self.init()
            self.execute()
            self.cleanup()
        except Exception as e:
            self.setStatus(self.STATE_ERROR, str(e))

        try:
            # XXX: Do always Qosium clean-up
            self.qosium.cleanup()
        except Exception as e:
            pass

    def init(self):
        """
        Initialize all sub-modules for experiment execution.

        Raises:
            Exception: If something goes wrong during initialization.
        """
        self.setStatus(self.STATE_INITIALIZE, None)

        # Initialize all sub-modules
        #self.osm.initialize(self.apps)
        self.qosium.initialize(self.slices)

        # Set DL/UL rate and burst values to zero in OvS (no limit)
        self.ovs.setDownlinkUplinkValues([
            #{"dl": {"rate": 400000, "burst": 75000}, "ul": {"rate": 60000, "burst": 11250}},
            #{"dl": {"rate": 400000, "burst": 75000}, "ul": {"rate": 60000, "burst": 11250}}
            {"dl": {"rate": 0, "burst": 0}, "ul": {"rate": 0, "burst": 0}},
            {"dl": {"rate": 0, "burst": 0}, "ul": {"rate": 0, "burst": 0}}
            #{"dl": {"rate": 100000, "burst": 18750}, "ul": {"rate": 60000, "burst": 11250}},
            #{"dl": {"rate": 100000, "burst": 18750}, "ul": {"rate": 60000, "burst": 11250}}
        ])

    def execute(self):
        """
        Execution loop of an experiment with AI-adjusted resource allocation.
        """
        while not self._stop_event.is_set():
            if datetime.now(timezone.utc) >= self.startTime:
                self.setStatus(self.STATE_EXECUTE, None)

                while datetime.now(timezone.utc) < self.stopTime and not self._stop_event.is_set():
                    try:
                        # If we have 2 slices, use AI-based resource allocation
                        if len(self.slices) == 2:
                            kpis = self.qosium.getKpisPerSlice()

                            self.setLog(f"Got KPIs from Qosium: {json.dumps(kpis)}")

                            # Get allocation for downlink and uplink

                            allocation = self.ai.processKpis(kpis)

                            dlSlice1 = allocation["downlink_allocation"]["slice1"]
                            dlSlice2 = allocation["downlink_allocation"]["slice2"]
                            ulSlice1 = allocation["uplink_allocation"]["slice1"]
                            ulSlice2 = allocation["uplink_allocation"]["slice2"]

                            logger.debug(f"Got DL slice allocation; Slice1={dlSlice1}, Slice2={dlSlice2}")
                            logger.debug(f"Got UL slice allocation; Slice1={ulSlice1}, Slice2={ulSlice2}")

                            #"""
                            self.adjustSwitchValues(dlSlice1, dlSlice2, ulSlice1, ulSlice2)

                            epoch_ms_now = time.time_ns() // 1_000_000

                            self.setLog(f"Set DL slice allocation; Time={epoch_ms_now}, Slice1={dlSlice1}, Slice2={dlSlice2}")
                            self.setLog(f"Set UL slice allocation; Time={epoch_ms_now}, Slice1={ulSlice1}, Slice2={ulSlice2}")
                            #"""
                    except Exception as e:
                        logger.warning(f"Recover from error in execute: {str(e)}")

                    time.sleep(self.config["updateIntervalSeconds"])

                break

            time.sleep(0.1)

    def cleanup(self):
        """
        Handle post-experiment processes (e.g., stopping Qosium and OSM).

        Raises:
            Exception: If something goes wrong during the cleanup process.
        """
        self.setStatus(self.STATE_CLEANUP, None)

        # Clean up all the sub-modules
        self.qosium.cleanup()
        #self.osm.cleanup()

        # Set DL/UL rate and burst values to zero in OvS (no limit)
        self.ovs.setDownlinkUplinkValues([
            {"dl": {"rate": 0, "burst": 0}, "ul": {"rate": 0, "burst": 0}},
            {"dl": {"rate": 0, "burst": 0}, "ul": {"rate": 0, "burst": 0}}
        ])

        self.setStatus(self.STATE_DONE, None)

    def start(self, nst):
        """
        Load the configuration and start the experiment thread.

        Args:
            nst (dict): Network Slice Template (NST) dictionary.

        Raises:
            Exception: If an experiment is already running.

        Returns:
            dict: The experiment ID and slice-specific information.
        """
        with self.runningLock:
            if self._thread != None:
                raise Exception("Can run only one experiment at a time!")

            self.load(nst)
            self.startThread()

            with self.statusLock:
                return {
                    "id": self.id,
                    "defaultSliceId": self.config["defaultSliceId"],
                    "slices": copy.deepcopy(self.slices)
                }

    def load(self, nst):
        """
        Load the experiment configuration from a Network Slice Template (NST).

        Args:
            nst (dict): The NST containing the experiment configuration.

        Raises:
            Exception: If the submitted NST contains invalid information.
        """
        with self.statusLock:
            self.id = None
            self.log = ""
            self.state = self.STATE_READY
            self.message = None
            self.nst = None
            self.slices = []
            self.apps = []

            # Check the received NST

            if "trialId" not in nst or not isinstance(nst["trialId"], int):
                raise Exception("Invalid or no trial ID in NST")

            # Start and stop times in NST are in the UTC timezone
            dt = datetime.strptime(nst["startTime"], "%Y-%m-%dT%H:%M:%SZ")
            self.startTime = dt.replace(tzinfo=timezone.utc)

            dt = datetime.strptime(nst["stopTime"], "%Y-%m-%dT%H:%M:%SZ")
            self.stopTime = dt.replace(tzinfo=timezone.utc)

            timeNow = datetime.now(timezone.utc)

            if timeNow > self.startTime or timeNow > self.stopTime:
                raise Exception("Invalid execution time in NST")

            if self.startTime > self.stopTime:
                raise Exception("Invalid execution time in NST")

            logger.debug(f"Experiment start time: {self.startTime} ({int(self.startTime.timestamp())})")
            logger.debug(f"Experiment stop time: {self.stopTime} ({int(self.stopTime.timestamp())})")

            if "slices" not in nst or not isinstance(nst["slices"], list) or "" in nst["slices"]:
                raise Exception("Invalid or no slice information in NST")

            if not all(isinstance(item, str) for item in nst["slices"]):
                raise Exception("Slice information in NST should contain only strings")

            if len(nst["slices"]) > 2:
                raise Exception("Only up to 2 slices supported")

            for index, item in enumerate(nst["slices"]):
                sliceId = self.config["slices"][index]["id"]
                self.slices.append({"type": item, "id": sliceId})

            if "applications" not in nst or not isinstance(nst["applications"], list):
                raise Exception("Invalid or no application information in NST")

            if not all(isinstance(item, str) for item in nst["applications"]):
                raise Exception("Application information in NST should contain only strings")

            if len(nst["applications"]) > 2:
                raise Exception("Only up to 2 applications supported")

            self.apps = nst["applications"]

            self.nst = nst

            # Only one experiment run at a time; use static ID
            self.id = 1

    def startThread(self):
        """
        Start an experiment thread (create a new thread and clear the stop signal).

        Raises:
            Exception: If the experiment thread is already running.
        """
        if self._thread != None:
            raise Exception("Experiment thread alredy running")

        self._stop_event.clear()
        self._thread = threading.Thread(target=self.run, daemon=True)
        self._thread.start()

    def stop(self, id):
        """
        Stop a running experiment: set the stop signal and join the experiment thread.

        Args:
            id (int): Identifier of the running experiment.

        Returns:
            str: Logs of the AI-assisted resource optimization run.

        Raises:
            Exception: If the ID of the running experiment is not found.
        """
        with self.runningLock:
            if self.id != id or self._thread is None:
                raise Exception("Experiment not found!")

            # Signal the experiment thread to stop
            self._stop_event.set()

            # Wait the experiment thread to finish
            self.join()

            # TODO: Replace with self.log
            log = self.getLog()

            # Clear all status variables
            with self.statusLock:
                self.id = None
                self.log = ""
                self.state = self.STATE_READY
                self.message = None
                self.nst = None
                self.slices = []
                self.apps = []

            self._thread = None
            return log

    def join(self):
        """
        Join the running experiment thread.

        Raises:
            Exception: If no joinable experiment thread is found.
        """
        if self._thread == None:
            raise Exception("No joinable experiment thread found!")

        self._thread.join()

    def adjustSwitchValues(self, dlSlice1, dlSlice2, ulSlice1, ulSlice2):
        """
        Send the slice-specific rate and burst values to the Open vSwitch
        responsible for DL/UL rate limiting.

        Args:
            dlSlice1 (float): Downlink allocation for slice 1.
            dlSlice2 (float): Downlink allocation for slice 2.
            ulSlice1 (float): Uplink allocation for slice 1.
            ulSlice2 (float): Uplink allocation for slice 2.
        """
        dlRateSlice1 = round(dlSlice1 * self.config["maxDownlinkBandwidth"])
        dlBurstSlice1 = calculateBurst(dlRateSlice1)
        dlRateSlice2 = round(dlSlice2 * self.config["maxDownlinkBandwidth"])
        dlBurstSlice2 = calculateBurst(dlRateSlice2)

        ulRateSlice1 = round(ulSlice1 * self.config["maxUplinkBandwidth"])
        ulBurstSlice1 = calculateBurst(ulRateSlice1)
        ulRateSlice2 = round(ulSlice2 * self.config["maxUplinkBandwidth"])
        ulBurstSlice2 = calculateBurst(ulRateSlice2)

        ovsValues = [
            {
                "dl": {"rate": dlRateSlice1, "burst": dlBurstSlice1},
                "ul": {"rate": ulRateSlice1, "burst": ulBurstSlice1}
            },
            {
                "dl": {"rate": dlRateSlice2, "burst": dlBurstSlice2},
                "ul": {"rate": ulRateSlice2, "burst": ulBurstSlice2}
            }
        ]

        logger.debug(f"Send rate/burst values to OvS: {ovsValues}")
        self.ovs.setDownlinkUplinkValues(ovsValues)

    def getStatus(self):
        """
        Get the status information of the running experiment.

        Returns:
            dict: The ID, state identifier, and message of the running experiment.
        """
        with self.statusLock:
            return {"id": self.id, "state": self.state, "message": self.message}

    def setStatus(self, state, message):
        """
        Set the status information (state and message) for the running experiment.

        Args:
            state (str): A state identifier.
            message (str): A string describing the current state.
        """
        with self.statusLock:
            self.state = state
            self.message = message

    def setLog(self, str):
        """
        Append a new line to the experiment log.

        Args:
            str (str): A string containing a single log entry.
        """
        now = datetime.now()

        # Create a timestamp string with milliseconds
        timestamp = now.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

        with self.statusLock:
            self.log += f"{timestamp}: {str}\n"

    def getLog(self):
        """
        Get the current experiment's log rows.

        Returns:
            str: All log rows.
        """
        with self.statusLock:
            return self.log
