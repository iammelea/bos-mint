from .. import Config
from datetime import datetime, timedelta
import requests

class Ping(object):

    CACHE = {}
    LAST_PING = None

    def __init__(self):
        self.ensure_ping()

    def ensure_ping(self):
        ping_interval_in_seconds = Config.get("dataproxy_link", "ping_interval_in_seconds", 300)
        if Ping.LAST_PING is None or datetime.utcnow() > Ping.LAST_PING + timedelta(ping_interval_in_seconds):
            self.ping()

    def ping(self):
        proxies = Config.get("dataproxy_link", "proxies", {})
        for provider_hash, proxy in proxies.items():
            try:
                isalive_url = proxy["endpoint"] + "/isalive?token=" + proxy["token"]
                replay_url = proxy["endpoint"] + "/replay?token=" + proxy["token"]
                response = requests.get(isalive_url)
                response = requests.get(replay_url)

                Ping.CACHE[provider_hash] = {"status": response.status_code,
                                             "replay": replay_url}
            except KeyError:
                pass
            except Exception as e:
                pass
        Ping.LAST_PING = datetime.utcnow()

    def get_status(self):
        return Ping.CACHE

    def get_replay_url(self, provider_hash, incident, call):
        try:
            if Ping.CACHE[provider_hash]["status"] == 200:
                replay_url = Ping.CACHE[provider_hash]["replay"]
                replay_url = replay_url + "&name_filter=" + incident["unique_string"] + "," + call
                replay_url = replay_url + "&restrict_witness_group=" + Config.get("connection", "use") 
                replay_url = replay_url + "&only_report=True"
                return replay_url
            else:
                return None
        except KeyError:
            return None
    