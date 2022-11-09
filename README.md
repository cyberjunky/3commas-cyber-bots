# 3Commas Cyber Bot Helpers <a href="https://github.com/cyberjunky/3commas-cyber-bots/blob/main/README.md#donate"><img src="https://img.shields.io/badge/Donate-PayPal-green.svg" height="40" align="right"></a> 

A collection of 3Commas bot helper scripts I wrote. (collection will grow over time)

<img src="images/robots.jpg"></a> 

## Disclaimer
```
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```
> My code is [MIT Licensed](LICENSE), read it please.

> Always test your setup and settings with your PAPER ACCOUNT first!

## Overview
This repository contains several Python scripts (bot helpers) which can be used to make your 3Commas bots more powerful -and hopefully more profitable-.

You can find a small description of each one below.  
They have their own documentation page in the wiki describing what it can do and how to use it in more detail .

## Why did you build these bot helpers?

Since I rather don't want to pay for Monthly services if this is not needed I started to write some scripts myself, learning more about Crypto along the way.


## Overview & Account management

Get overview and statistics in order to get an overview and manage your account and funds easily.

### Balance Report (balancereport.py)
A script which examins the connected exchanges, bots and deals on your account. Based on al this data, an overview is generated of funds in use and the amount available.

![BalanceReport](images/balancereport.png)

[BalanceReport Documentation](https://github.com/cyberjunky/3commas-cyber-bots/wiki/BalanceReport)


## Bot Pair changers

Change pairs of your bot(s) matching configured rankings and/or thresholds.

### AltRank (altrank.py)
A script which allows you to change the pairs of your 3Commas bot(s) at regular intervals using [LunarCrush](https://lnr.app/s/o3p1V2) AltRank rankings.

![AltRank](images/altrank.png)

[AltRank Documentation](https://github.com/cyberjunky/3commas-cyber-bots/wiki/AltRank)

### GalaxyScore (galaxyscore.py)
A script which allows you to change the pairs of your 3Commas bot(s) at regular intervals using [LunarCrush](https://lnr.app/s/o3p1V2) GalaxyScore rankings.

![GalaxyScore](images/galaxyscore.png)

[GalaxyScore Documentation](https://github.com/cyberjunky/3commas-cyber-bots/wiki/GalaxyScore)

### CoinMarketCap (coinmarketcap.py)
A script which allows you to change the pairs of your 3Commas bot(s) at regular intervals using [CoinMarketCap](https://coinmarketcap.com) rankings.

![CoinMarketCap](images/coinmarketcap.png)

[CoinMarketCap Documentation](https://github.com/cyberjunky/3commas-cyber-bots/wiki/CoinMarketCap)

### BotAssistExplorer (botassistexplorer.py)
A script which allows you to change the pairs of your 3Commas bot(s) at regular intervals using [3CTools's BotAssistExplorer](https://www.3c-tools.com/markets/bot-assist-explorer) rankings.

![BotAssistExplorer](images/botassistexplorer.png)

[BotAssistExplorer Documentation](https://github.com/cyberjunky/3commas-cyber-bots/wiki/BotAssistExplorer)


## Stoploss and Profit trailing

Change stoploss and/or takeprofit settings of your bot(s) using their running deals statistics.

### Futures Trailing stoploss (trailingstoploss.py)
A script which tracks active Future deals from your 3Commas bot(s) and change the stoploss when the profit thresholds are reached.

[TrailingStopLoss Documentation](https://github.com/cyberjunky/3commas-cyber-bots/wiki/TrailingStopLoss)

### DCA Trailing stoploss and profit (trailingstoploss_tp.py)
Same for DCA type deals but also including an implementation of a trailing take profit.

![Trailingstoploss_tp](images/trailingstoploss_tp.png)

[TrailingStopLoss and TakeProfit Documentation](https://github.com/cyberjunky/3commas-cyber-bots/wiki/TrailingStopLoss-and-TakeProfit)


## Compounding

Add any profits made to your bot(s)

### Compound (compound.py)
This scripts checks closed deals of specified bot(s) at regular intervals and compounds any profits made, respecting BO/SO ratios or even change Maximum deal settings if configured.

[Compound Documentation](https://github.com/cyberjunky/3commas-cyber-bots/wiki/Compound)

## Watchlists

Trigger starting and/or stopping of bot deals using external trigger messages.


### Watchlist (watchlist.py)
This will monitor a specific Telegram chat channel (https://t.me/wiseanalize) and sent a 'start new deal' trigger to the linked bot(s) for that pair.

[Watchlist Documentation](https://github.com/cyberjunky/3commas-cyber-bots/wiki/Watchlist)

### Watchlist 100eyes (watchlist_100eyes.py)
This will monitor a Telegram chat channels provided by (https://www.100-eyes.com/) and sent a 'start new deal' trigger to the linked bot(s) for that pair.

[Watchlist 100eyes Documentation](https://github.com/cyberjunky/3commas-cyber-bots/wiki/Watchlist-100eyes)

### Watchlist Hodloo (watchlist_hodloo.py)
It will monitor a specific Hodloo Telegram chat channel (https://qft.hodloo.com/alerts/) and sent a 'start new deal' trigger to the linked bot for that pair.

[Watchlist Hodloo Documentation](https://github.com/cyberjunky/3commas-cyber-bots/wiki/Watchlist-Hodloo)

### Watchlist Telegran (watchlist_telegram.py)
Combination of watchlist and watchlist_hodloo script.

[Watchlist Telegram Documentation](https://github.com/cyberjunky/3commas-cyber-bots/wiki/Watchlist-Telegram)


## Binance account Setup

-   Create a [Binance account](https://accounts.binance.com/en/register?ref=156153717) (Includes my referral, I'll be super grateful if you use it).
-   Enable Two-factor Authentication.
-   Create a new API key.
-   Get a stable cryptocurrency to trade with.

NOTE: Only needed if you want to trade on Binance, not needed for the functionality of the bot(s).

## FTX account Setup

-   Create a [FTX account](https://ftx.com/#a=38250549) (Includes my referral, I'll be super grateful if you use it).
-   Enable Two-factor Authentication.
-   Create a new API key.
-   Get a stable cryptocurrency to trade with.

NOTE1: Only needed if you want to trade on FTX, not needed for the functionality of the bot(s).
NOTE2: When you connect your FTX account to 3Comma's you get free use to trade on FTX, no need to have a 3Commas subscription.

## 3Commas account Setup

-   Create a [3Commas account](https://3commas.io/?c=tc587527) (Includes my referral, again I'll be super grateful if you use it).
-   Enable Two-factor Authentication.
-   Connect your 3Commas account with the Binance or FTX exchange using the key values created above.
-   Create a new API key with Bot Read, Bot Write and Account Read permissions, enther these key in config.py
-   Setup a DCA Bot (details will follow)

NOTE: Needed for the bot(s) to work, duh they are 3Commas bot helpers.

## LunarCrush account Setup
Support the Project
-   Create a [LunarCrush account](https://lnr.app/s/o3p1V2) (Includes my referral, again I'll be super grateful if you use it).
-   Create a API key under https://lunarcrush.com/developers/api/authentication and add it to your altrank.ini or galayscore.ini

This account is needed for the bot(s) to work, to download the GalaxyScore and/or AltRank information.

NOTE: It seems LunarCrush have phased out their free older API functionality at 1 Nov 2022, and now only allows API v3 access -which the latest scripts support- but API calls are not free anymore.
We are investigating options.

## Bot helper setup

### Download and install

You need run Python 3.7 or higher.

Download the zip file of the latest release from [here](https://github.com/cyberjunky/3commas-cyber-bots/releases) and unpack it, or do a `git clone` with the steps described below.

```
$ sudo apt install git
$ git clone https://github.com/cyberjunky/3commas-cyber-bots.git
$ cd 3commas-cyber-bots
$ pip3 install -r requirements.txt
```

### Configuration of the bot helpers

For a new install just start the bot helper you want to use like below for altrank, a config file with the name of bot is created (ending in .ini)

```
$ python3 ./altrank.py
```

Then you can edit the file and start the bot helper again to use it.

Look at the helper sections above for each layout and description of the settings.


### 3Commas API key permissions needed
The 3Commas API need to have 'BotsRead, BotsWrite and AccountsRead' permissions, don't give it more than that to be safe.  
BotsRead: Required to get a list of all bots.  
BotsWrite: Required to update bot pairs.  
AccountsRead: Required to get connected exchanges to ensure that pairs are valid.  

### Telegram ID, Hash and Secrets explained
There are two sets of Telegram related settings.

#### Watchlist
One is used by `watchlist.py`, `watchlist_hodloo` or `watchlist_telegram` to connect to the telegram API.

To get the Telegram App ID and hash you have to create an application ,

These are the steps as outlined in below link:

-   Login to your Telegram account [here](https://my.telegram.org/) with the phone number of the developer account to use.
-   Visit the [API development tools](https://my.telegram.org/apps)
-   A Create new application window will appear. Fill in your application details. There is no need to enter any URL, and only the first two fields (App title and Short name) can currently be changed later.
-   Click on Create application at the end. Remember that your API hash is secret and Telegram won’t let you revoke it. Don’t post it anywhere!

Fill these in here inside watchlist.ini:
```
tgram-api-id = 1234566
tgram-api-hash = o6la4h1158ylt4mzhnpio6la
```

#### Notifications
The other set of values are used by to sent notifications to Telegram channel of your choice.
I use Apprise for this, all possible platform to send notifications to are described here [Apprise website](https://github.com/caronc/apprise)

The Telegram part is described [here](https://github.com/caronc/apprise/wiki/Notify_telegram#account-setup)

-   First you need to create a bot to get a bot_token
-   Open telegram and search for 'BotFather' start a conversation
-   Type: /newbot
-   Answer the questions it asks after doing this (which get the name of it, etc).
-   When you've completed step 2, you will be provided a bot_token that looks something like this: 123456789:alphanumeric_characters.
-   Type /start now in the same dialog box to enable and instantiate your brand new bot.

Fill in the notify-url like this:
```
notify-urls = [ "tgram://2097657222:AAFSebMCJF6rQ6l46n21280K8y59Mg6w13112w/"]

```
Now you also need a chat_id, don't worry Apprise can get this for you.
-   First sent a random message to your bot via the Telegram app.
-   Then start one of the bot helpers with above like notify-url setting.
and look at the logs, it should contain something like:
```
2021-11-11 19:39:02,930 - apprise - INFO - Detected Telegram user R (userid=936303417)
2021-11-11 19:39:02,930 - apprise - INFO - Update your Telegram Apprise URL to read: tgram://2...w/%40936302121/?image=False&detect=yes&format=text&overflow=upstream&rto=4.0&cto=4.0&verify=yes
```
-   Now copy and paste the whole part behind and including the % and paste it behind the notify-url you had configured, to avoid syntax errors you need to put an extra % in between so ...w/%%409... etc...

If you didn't send a message to your bot first this is what the logs show:
```
2021-11-11 19:35:14,682 - apprise - WARNING - Failed to detect a Telegram user; try sending your bot a message first.
2021-11-11 19:35:14,682 - apprise - WARNING - There were not Telegram chat_ids to notify.
```

### Running the bot helpers

#### Run Manually
`$ python3 ./galaxyscore.py`
and/or
`$ python3 ./altrank.py`
and/or
`$ python3 ./watchlist.py`
and/or
`$ python3 ./compound.py`

They also have some command-line options:

```
./galaxyscore.py -h
usage: galaxyscore.py [-h] [-d DATADIR] [-s SHAREDIR] [-b BLACKLIST]

Cyberjunky's 3Commas bot helper.

optional arguments:
  -h, --help            show this help message and exit
  -d DATADIR, --datadir DATADIR
                        directory to use for config and logs files
  -s SHAREDIR, --sharedir SHAREDIR
                        directory to use for shared files between scripts
  -b BLACKLIST, --blacklist BLACKLIST
                        local blacklist to use instead of 3Commas's
```

The blacklist file layout is one pair per line.

### Example output for `altrank`
```
2021-10-14 19:05:11,922 - altrank - INFO - 3Commas altrank bot helper!
2021-10-14 19:05:11,922 - altrank - INFO - Started at Thursday 19:05:11 14-10-2021
2021-10-14 19:05:11,922 - altrank - INFO - Loaded configuration from 'altrank.ini'
2021-10-14 19:05:11,922 - altrank - INFO - Using PAPER TRADING account mode
2021-10-14 19:05:11,922 - altrank - INFO - Notifications are enabled
2021-10-14 19:05:12,372 - altrank - INFO - Fetched LunarCrush Top X ar OK (50 coins)
2021-10-14 19:05:12,425 - altrank - INFO - Fetched 3Commas pairs blacklist OK (52 pairs)
2021-10-14 19:05:12,478 - altrank - INFO - Finding the best pairs for Binance exchange
2021-10-14 19:05:12,509 - altrank - INFO - Fetched 3Commas market data for binance OK (1262 pairs)
2021-10-14 19:05:12,510 - altrank - INFO - Bot 'BUSD Bull Long AltRank' with id '1234567' is already using the best pairs
2021-10-14 19:05:12,510 - altrank - INFO - Next update in 3600 Seconds at 20:05:12

```

#### Start Automatically

Example service files `3commas-galaxyscore-bot.service`, `3commas-altrank-bot.service` (and `3commas-galaxyscore-env-bot.service`, `3commas-altrank-env-bot.service` if you use the .env enviroment described above) are provided,. They can all be found in the `scripts` directory, you need to edit the paths and your user inside them to reflect your install. And install the service you need as describe below.

```
$ sudo cp scripts/3commas-galaxyscore-bot.service /etc/systemd/system/
$ sudo systemctl start 3commas-galaxyscore-bot.service
$ sudo cp scripts/3commas-altrank-bot.service /etc/systemd/system/
$ sudo systemctl start 3commas-altrank-bot.service
```
Example on how to enable starting the bot helper(s) at boot:
```
$ sudo systemctl enable 3commas-galaxyscore-bot.service
$ sudo systemctl enable 3commas-altrank-bot.service
```
Example on how to disable starting the bot helper(s) at boot:
```
$ sudo systemctl disable 3commas-galaxyscore-bot.service
$ sudo systemctl disable 3commas-altrank-bot.service
```
How to check status:
```
$ systemctl status 3commas-galaxyscore-bot.service 
● 3commas-galaxyscore-bot.service - 3Commas GalaxyScore Daemon
     Loaded: loaded (/etc/systemd/system/3commas-galaxyscore-bot.service; enabled; vendor preset: enabled)
     Active: active (running) since Thu 2021-10-14 20:09:43 CEST; 39s ago
   Main PID: 53347 (python3)
      Tasks: 2 (limit: 18361)
     Memory: 29.3M
     CGroup: /system.slice/3commas-galaxyscore-bot.service
             └─53347 /usr/bin/python3 /home/ron/development/3commas-cyber-bots/galaxyscore.py

okt 14 20:09:43 laptop-ubuntu python3[53347]: 2021-10-14 20:09:43,713 - galaxyscore - INFO - Using PAPER TRADING account mode
okt 14 20:09:43 laptop-ubuntu python3[53347]: 2021-10-14 20:09:43,713 - galaxyscore - INFO - Notifications are enabled
okt 14 20:09:44 laptop-ubuntu python3[53347]: 2021-10-14 20:09:44,559 - galaxyscore - INFO - Fetched LunarCrush Top X gs OK (50 coins)
okt 14 20:09:44 laptop-ubuntu python3[53347]: 2021-10-14 20:09:44,637 - galaxyscore - INFO - Fetched 3Commas pairs blacklist OK (52 pairs)
okt 14 20:09:44 laptop-ubuntu python3[53347]: 2021-10-14 20:09:44,721 - galaxyscore - INFO - Finding the best pairs for Binance exchange
okt 14 20:09:44 laptop-ubuntu python3[53347]: 2021-10-14 20:09:44,761 - galaxyscore - INFO - Fetched 3Commas market data for binance OK (1262 pairs)
okt 14 20:09:44 laptop-ubuntu python3[53347]: 2021-10-14 20:09:44,761 - galaxyscore - INFO - Updating your 3Commas bot(s)
okt 14 20:09:44 laptop-ubuntu python3[53347]: 2021-10-14 20:09:44,886 - galaxyscore - INFO - Bot 'BUSD Bull Long TTP - 766 - GalaxyScore' with id '6395939' updated with these pairs:
okt 14 20:09:44 laptop-ubuntu python3[53347]: 2021-10-14 20:09:44,887 - galaxyscore - INFO - ['BUSD_HBAR', 'BUSD_PERP', 'BUSD_RLC', 'BUSD_COTI', 'BUSD_AXS', 'BUSD_QNT', 'BUSD_ETH', 'BUSD_QUICK', 'BUSD_OCEAN', 'BUSD_CRV']
okt 14 20:09:44 laptop-ubuntu python3[53347]: 2021-10-14 20:09:44,887 - galaxyscore - INFO - Next update in 3600 Seconds at 21:11:44

```

How to check logs:
```
$ sudo journalctl -u 3commas-galaxyscore-bot.service 
```

How to edit an already installed service file:
```
$ sudo systemctl edit --full 3commas-galaxyscore-bot.service 
```

### Need for multiple settings

If you want a set of bots having 20 pairs of AltRank/GalaxyScore and another set use 10, or want to trigger on multiple Telegram channels, you can simply copy the script and use a descriptive name, it will create and use it's own settings file, and logfile... as long as the original name is in the file name.
```
e.g.
$ cp altrank.py altrank10.py
$ ./altrank10.py 
2021-11-20 13:22:37 - altrank10.py - 3Commas bot helper altrank10!
2021-11-20 13:22:37 - altrank10.py - Started at Saturday 13:22:37 20-11-2021.
2021-11-20 13:22:37 - altrank10.py - Created example config file 'altrank10.ini', edit it and restart the program.

$ cp scripts/3commas-altrank-bot.service script/3commas-altrank10-bot.service
And change ExecStart entryr accordingly
```

### Options for hosting this

- Intel NUC, install Debian or Ubuntu without GUI.
  And follow installation steps above.
  
- Raspberry Pi, install the Raspberry Pi OS
  And follow installation steps above.

- Docker find all settings and [documentation here](docker/)



In the Cloud, if you are willing to store your config files with your API keys in the Cloud, these are some options:

- PythonAnywhere https://eu.pythonanywhere.com/ Create free account, click on 'Bash' button and do:
```
$ git clone https://github.com/cyberjunky/3commas-cyber-bots.git
$ cd 3commas-cyber-bots
$ pip3 install -r requirements.txt
```
  Then you can run any of the scripts.
  More instructions can be found here https://www.youtube.com/watch?v=NH2PhXYvrWs, if you want to run multiple bot helpers, create another Bash console by clicking on the 'Bash' button again, cd to the 3commas-cyber-bots folder and start the next.
  Please visit the wiki for more information [Wiki PythonAnywhere](https://github.com/cyberjunky/3commas-cyber-bots/wiki/PythonAnywhere)
  
- Google Cloud https://console.cloud.google.com Login with your gmail adress,goto 'Compute Engine', 'VM instances', create 
  You can create a small sized VM, you need to specify your CC details.
  More instructions can be found here https://www.youtube.com/watch?v=5OL7fu2R4M8
  NOTE: From Europe there are no free VM's available as shown in the video, at least I could not find them.


### Run from Python Enviroment (optional)

You can use the install script called setup.sh to create this environment. Simply run it as ./setup.sh and you have the options:
```
usage:
	-i,--install    Install 3commas-cyber-bots from scratch
	-u,--update     Command git pull to update.
```
It creates a .env python enviroment to install the requirements in, and you can run the scripts from there without cluttering your machine.

Before running any of the scripts manually enter the virtual environment first
```
cd 3commas-cyber-bots
source .env/bin/activate
```

### TODO
- You tell me, I'm open for ideas and requests!

### FAQ

1) I get this when I try to start the bot:
```
Traceback (most recent call last):
  File "./galaxyscore.py", line 7, in <module>
    from py3cw.request import Py3CW
ModuleNotFoundError: No module named 'py3cw'
```
Install the python requirements like so:
``` 
$ pip3 install -r requirements.txt
```
Or run `setup.sh` script to install the Python environent with everything in it.

2) I get this error:
```
Fetching 3Commas pairs blacklist failed with error: {'error': True, 'msg': 'Other error occurred: api_key_invalid_or_expired Unauthorized. Invalid or expired api key. None.'}
```

Something is wrong with your 3Commas API keys, check the API key values in your `config.ini` file, you can paste them there without the " " 

3) I get this error:
```
  File "/usr/lib/python3.7/logging/init.py", line 1121, in _open
    return open(self.baseFilename, self.mode, encoding=self.encoding)
FileNotFoundError: [Errno 2] No such file or directory: '/home/pi/3commas-cyber-bots/logs/galaxyscore.log'
```

Create the 'logs' directory inside the bot folder.

4) I use telegram notifications and get the message:
```
Detected Telegram user R (userid=123456789)
2021-10-13 21:20:05,573 INFO - Update your Telegram Apprise URL to read: tgram://2...w/%123456789/?image=False&detect=yes&format=text&overflow=upstream&rto=4.0&cto=4.0&verify=yes
```
Apply the part behind and including the % to your tgram url in the config, but add another % infront of the % to suppress parse errors like this:
```
   raise InterpolationSyntaxError(
configparser.InterpolationSyntaxError: '%' must be followed by '%' or '(', found: '%123456789/?image=False&detect=yes&format=text&overflow=upstream&rto=4.0&cto=4.0&verify=yes" ]'
```

So it looks something like this: (strings are bogus)
```
notify-urls = [ "tgram://9995888120:BoJPor6opeHyxx5VVZPX-BoJPor6opeHyxx5VVZPX/%%123456789/?image=False&detect=yes&format=text&overflow=upstream&rto=4.0&cto=4.0&verify=yes" ]
```

5) I get this error running pip3 install step:
```
       #include <ffi.h>
                ^~~~~~~
      compilation terminated.
      error: command 'x86_64-linux-gnu-gcc' failed with exit status 
```

Install libffi-dev with `sudo apt install libffi-dev` and try again.

6) I get error 'can't find Rust compiler':

Update pip3 like so:
```
$ pip3 install --upgrade pip
```
And try again.

6) After running the watchlist.py script for a few days, the following errors sometimes shows up in the logs:
```
Error occurred while triggering start_new_deal bot 'Bot name' error: Other error occurred: Unknown error occurred#Exceptions::OpenDealPresentForThisPair None None.
```
This happens when your bot is in a paper trade account, `watchlist` will then ignore the exchange field in the trigger, so when two of the same pairs for different exchanges are triggered, you get the same pair twice, and 3Commas tells you that you already have a trade for this pair, this only happens in paper mode.

7) I get error 'TypeError: object of type 'int' has no len()'
```
  File "./*.py", line 511, in callback
    if len(botids) == 0:
TypeError: object of type 'int' has no len()
```
Make sure usdt-botids and btc-botids are defined within [] in your ini files.

8) I get error `for account in data: TypeError: 'NoneType' object is not iterable`
```
  File "./*.py", line 250, in get_threecommas_account
    for account in data:
TypeError: 'NoneType' object is not iterable
```
Newer versions of the scripts also need AccountRead permissions for the 3Commas API Keys.
Create new ones, with it and paste them in your ini file(s)

9) I get error `Error occurred updating bots: Other error occurred: signature_invalid Provided signature is invalid None.`  
The secret key specified for the 3Commas API is invalid, check for possible paste error.

10) I get error `2022-01-11 00:11:00 - altrank - Fetching LunarCrush data failed with error: 401 Client Error: Unauthorized for url: https://api.lunarcrush.com/v2?data=market&type=fast&sort=acr&limit=150&key=Your+LunarCrush+API+Key`
LunarCrush now expect a valid apikey again, create an account here [LunarCrush](https://lnr.app/s/o3p1V2) and login to https://legacy.lunarcrush.com/, then goto settings and API tab, create key and use this in altrank.ini and/or galaxyscore.ini.

### Debugging

Set debug to True in config.ini and check the appropriate log file under `logs/` for debug information
```
debug = True
```

## Donate
If you enjoyed this project -and want to support further improvement and development- consider sending a small donation using the PayPal button or one of the Crypto Wallets below. :v:
<a href="https://www.paypal.me/cyberjunkynl/"><img src="https://img.shields.io/badge/Donate-PayPal-green.svg" height="40" align="right"></a>  

Wallets:

- USDT (TRC20): TEQPsmmWbmjTdbufxkJvkbiVHhmL6YWK6R
- USDT (ERC20): 0x73b41c3996315e921cb38d5d1bca13502bd72fe5

- BTC (BTC)   : 18igByUc1W2PVdP7Z6MFm2XeQMCtfVZJw4
- BTC (ERC20) : 0x73b41c3996315e921cb38d5d1bca13502bd72fe5

Free crypto:
Or at least join my Pi mining team, it's free:

<img src="images/pi-icon.png" height="48" align="left"> 1π! Pi is a new digital currency developed by Stanford PhDs, with over 25 million members worldwide. To claim your Pi, follow this link https://minepi.com/cyberjunky and use my username (cyberjunky) as your invitation code. 

Claim free crypto (Hi Dollars) every day by answering a simple daily question. https://hi.com/cyberjunky  

My referral links: (gives you discount and/or less fees to pay):

- [Prosum Solutions Indicators](https://prosum-solutions.store/ref/ron.klinkien/?campaign=cyberbothelpers) Excellent TradingView indicators QFL Base Breaking, Price Change Scalper, 3Commas DCA, and more.. have a look and try them! Featured in TheTradingParot video's. Use above link and coupon code: DJWNGFHXTI for 15% discount!

  Look here for instruction video(s): [Prosum Solutions YouTube Channel](https://www.youtube.com/channel/UCUoCoHjp67pQwYJQgpsrz1w/videos)

- [LunarCrush](https://lnr.app/s/o3p1V2) Earn points
- [Binance](https://accounts.binance.com/en/register?ref=156153717)
- [FTX](https://ftx.com/#a=38250549) Get 5.00% fee discount
- [3Commas](https://3commas.io/?c=tc587527) Get 10% discount for first monthly subscription
- [Bybit](https://www.bybit.com/en-US/invite?ref=QXGO00) Give $20
- [Bitvavo](https://bitvavo.com/?a=90A596F835) No fees over €1000 trading in first week
- [TradingView](https://www.tradingview.com/gopro/?share_your_love=cyberjunkynl) Get up to $30 each after they upgrade to a paid plan
- [CoinMaketCap](https://coinmarketcap.com/invite?ref=3IYRT0KW) Earn rewards together!

## Disclamer (Reminder)
```
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```
> My code is [MIT Licensed](LICENSE), read it please.

> Always test your settings with your PAPER ACCOUNT first!
