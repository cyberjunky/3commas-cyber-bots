"""
Cyberjunky's 3Commas websocket helper.
Updated by SanCoca
"""
import json
import logging
import hashlib
import hmac
import threading
from base64 import b64encode
from typing import Callable, Dict, Literal
from Crypto.Signature import pkcs1_15
from Crypto.Hash import SHA256
from Crypto.PublicKey import RSA

import rel
import websocket

_LOGGER = logging.getLogger(__name__)

SocketChannels = Literal["DealsChannel","SmartTradesChannel"]
SocketChannelsTuple = ("DealsChannel", "SmartTradesChannel")
SocketPaths = Literal['/deals', '/smart_trades']

channel_paths: Dict[SocketChannels, SocketPaths] = {
    "DealsChannel": "/deals",
    "SmartTradesChannel": "/smart_trades"
}

def construct_socket_data(
        api_key: str,
        api_secret: str,
        api_selfsigned: str,
        channel:SocketChannels = "DealsChannel",
    ):
    """
    Construct websocket identifier
    """
    _channel_path = channel_paths[channel]
    _signature = None

    if not api_selfsigned:
        _encoded_key = str.encode(api_secret)
        _message = str.encode(_channel_path)
        _signature = hmac.new(_encoded_key, _message, hashlib.sha256).hexdigest()
    else:
        _encoded_key = RSA.import_key(api_selfsigned)
        _message = str.encode(_channel_path)
        h = SHA256.new(_message)
        signer = pkcs1_15.new(_encoded_key)
        _signature = b64encode(signer.sign(h)).decode('utf-8')

    _id_data={
        'api_key': api_key,
        'signature': _signature
    }
    _users=[_id_data]
    _identifier = {
        'channel': channel,
        'users': _users
    }
    return _identifier

class ThreeCommasWebsocket:
    """
    Handle 3commas websocket events and data
    """

    is_running = True

    def __init__(self, on_event=None, identifier=None, seperate_thread=False):
        """
        :param on_event: function that get's called on received event
        """
        self.on_event = on_event
        self.websocket = None
        self.websocket_thread = None
        self._url = 'wss://ws.3commas.io/websocket'
        self.identifier = identifier
        self.seperate_thread = seperate_thread

    def __run_forever_rel_dispatcher(self):
        """
        Run forever websocket using dispatcher rel
        """
        self.websocket.run_forever(dispatcher=rel)  # Set dispatcher to automatic reconnection
        rel.signal(2, rel.abort)  # Keyboard Interrupt
        rel.dispatch()

    def __run_forever_thread_daemon(self):
        """
        Run forever using thread daemon
        """
        self.websocket_thread = threading.Thread(target=self.websocket.run_forever)
        self.websocket_thread.daemon = True
        self.websocket_thread.start()

    def __refresh(self):
        self.websocket = websocket.WebSocketApp(
            self._url,
            on_open=self.__on_open,
            on_error=self.__on_error,
            on_message=self.__on_message,
            on_close=self.__on_close,
        )

        if self.seperate_thread:
            self.__run_forever_thread_daemon()
        else:
            self.__run_forever_rel_dispatcher()


    def start(self):
        """
        Start websocket client
        """
        _LOGGER.debug("Websocket client start")

        self.is_running = True
        self.__refresh()


    def stop(self):
        """
        close websocket
        """
        self.is_running = False
        self.websocket.close()
        _LOGGER.debug("Websocket client stopped")

    def __on_open(self, ws):
        """
        On websocket open
        """
        _LOGGER.debug("Websocket open")

    def __on_close(self, ws, close_status_code, close_msg):
        """
        On Close Listener
        """
        if self.is_running:
            _LOGGER.debug("Websocket restart after close")

            self.__refresh()


    def __on_message(self, ws, message):
        """
        On message event
        """
        # _LOGGER.debug(f"Websocket data: {message}")
        try:
            message = json.loads(message)
            if "type" not in message:
                if (
                    "identifier" in message
                    and json.loads(message["identifier"])["channel"]
                    in SocketChannelsTuple
                ):
                    event = message["message"]
                    self.on_event(event)

                else:
                    _LOGGER.debug("Malformed data received\n%s", message)

            elif message["type"] == "welcome":
                _LOGGER.debug("Subscribing to the %s", self.identifier['channel'])
                self.websocket.send(
                    json.dumps({
                        "command": "subscribe",
                            "identifier": json.dumps(self.identifier),
                        }
                    )
                )
            elif message["type"] == "confirm_subscription":
                _LOGGER.debug("Succesfully subscribed %s", self.identifier['channel'])

            elif message["type"] == "ping":
                pass

            else:
                _LOGGER.debug("Received unknown type: %s", message)

        # Need better exception handling here
        except Exception as error:
            _LOGGER.exception(error)


    def __on_error(self, ws, error):
        """
        On Error listener
        :param error:
        """
        _LOGGER.debug("Websocket error: %s", error)


class ThreeCommasWebsocketHandler():
    """
    Three commas websocket master handler
    Default channel: DealsChannel
    """
    external_event_handler = None
    _data = None
    listener = None
    def __init__(
        self,
        api_key: str,
        api_secret: str,
        api_selfsigned: str,
        external_event_handler: Callable[[Dict], None] = None,
        channel: SocketChannels = "DealsChannel"
    ):
        if not api_key:
            raise SystemError("Api key missing")
        if (api_secret is None or api_secret == '') and (api_selfsigned is None or api_selfsigned == ''):
            raise SystemError("Api secret or private key missing")
        if channel not in SocketChannelsTuple:
            raise SystemError(f"Incorrect/unsupported stream channel {channel}")

        self.identifier = construct_socket_data(
            api_key=api_key,
            api_secret=api_secret,
            api_selfsigned=api_selfsigned,
            channel=channel
        )
        self.external_event_handler = external_event_handler


    def on_event(self, data):
        """
        On websocket event received
        """
        _LOGGER.debug("3Commas websocket update received: %s", data)
        self._data = data


    def start_listener(self, seperate_thread = False):
        """
        Spawn a new Listener and links it to self.on_trade.
        """
        event_handler = self.external_event_handler \
            if self.external_event_handler \
            else self.on_event

        self.listener = ThreeCommasWebsocket(
            event_handler,
            identifier=self.identifier,
            seperate_thread=seperate_thread
        )
        _LOGGER.debug("Starting listener")
        self.listener.start()
