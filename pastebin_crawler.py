#!/usr/bin/env python3
from math import ceil,fmod,fabs
from optparse import OptionParser
import os
import re
import time,datetime
import dateutil.relativedelta
import sys
import urllib
import urllib.request
import tarfile
import random
import signal

from pyquery import PyQuery


def get_timestamp():
    return time.strftime('%Y/%m/%d %H:%M:%S')

def all_python_encodings():
     return ["ascii",
             "iso8859_1",
             "cp1252",
             "utf_8",
             "utf_16",
             "utf_32",
             "cp1251",
             "shift_jis",
             "euc_jp",
             "euc_kr",
             "gb2312",
             "gbk",
             "gb18030",
             "latin_1",
             "iso8859_2",
             "cp1250",
             "iso8859_15",
             "cp1256",
             "iso8859_9",
             "cp1254",
             "big5",
             "cp874",
#             "big5hkscs",
#             "cp037",
#             "cp424",
#             "cp437",
#             "cp500",
#             "cp720",
#             "cp737",
#             "cp775",
#             "cp850",
#             "cp852",
#             "cp855",
#             "cp856",
#             "cp857",
#             "cp858",
#             "cp860",
#             "cp861",
#             "cp862",
#             "cp863",
#             "cp864",
#             "cp865",
#             "cp866",
#             "cp869",
#             "cp875",
#             "cp932",
#             "cp949",
#             "cp950",
#             "cp1006",
#             "cp1026",
#             "cp1140",
#             "cp1253",
#             "cp1255",
#             "cp1257",
#             "cp1258",
#             "euc_jis_2004",
#             "euc_jisx0213",
#             "hz",
#             "iso2022_jp",
#             "iso2022_jp_1",
#             "iso2022_jp_2",
#             "iso2022_jp_2004",
#             "iso2022_jp_3",
#             "iso2022_jp_ext",
#             "iso2022_kr",
#             "iso8859_3",
#             "iso8859_4",
#             "iso8859_5",
#             "iso8859_6",
#             "iso8859_7",
#             "iso8859_8",
#             "iso8859_10",
#             "iso8859_13",
#             "iso8859_14",
#             "iso8859_16",
#             "johab",
#             "koi8_r",
#             "koi8_u",
#             "mac_cyrillic",
#             "mac_greek",
#             "mac_iceland",
#             "mac_latin2",
#             "mac_roman",
#             "mac_turkish",
#             "ptcp154",
#             "shift_jis_2004",
#             "shift_jisx0213",
             "utf_32_be",
             "utf_32_le",
             "utf_16_be",
             "utf_16_le",
             "utf_7",
             "utf_8_sig"]


class Logger:
    verbose = False
    shell_mod = {
        '':'',
       'PURPLE' : '\033[95m',
       'CYAN' : '\033[96m',
       'DARKCYAN' : '\033[36m',
       'BLUE' : '\033[94m',
       'GREEN' : '\033[92m',
       'YELLOW' : '\033[93m',
       'RED' : '\033[91m',
       'BOLD' : '\033[1m',
       'UNDERLINE' : '\033[4m',
       'RESET' : '\033[0m'
    }
    def __init__(self,verbose=False):
        self.verbose = verbose

    def log ( self, message, is_bold=False, color='', log_time=True):
        prefix = ''
        suffix = ''
        logfile = 'pastebin_crawler.log'

        if log_time:
            prefix += '[{:s}] '.format(get_timestamp())

        if os.name == 'posix':
            if is_bold:
                prefix += self.shell_mod['BOLD']
            prefix += self.shell_mod[color.upper()]

            suffix = self.shell_mod['RESET']

        message = prefix + message + suffix
        #print ( message )
        #sys.stdout.flush()

        if (self.verbose == True) or (is_bold == True):
## tar log files if the size reachs 128MB
            size = os.path.getsize(logfile) or 0
            if size > 1024*1024*128:
                tarf = logfile+'.gz'
                mode='w:gz'
                with tarfile.open(tarf,mode) as out:
                    out.add(logfile)
                os.remove(logfile)
            with open(logfile, "a+") as logf:
                logf.write(message+"\n")

    def match(self, err):
        self.log(err, True, 'CYAN')

    def warn(self, err):
        self.log(err, True, 'YELLOW')

    def error(self, err):
        self.log(err, True, 'RED')

    def fatal_error(self, err):
        self.error(err)
        exit()

class Crawler:

    PASTEBIN_URL = 'http://pastebin.com'
    PASTES_URL = PASTEBIN_URL + '/archive'
    PASTESRAW_URL = PASTEBIN_URL + '/raw'
    REGEXES_FILE = 'regexes.txt'
    OK = 1
    ACCESS_DENIED = -1
    CONNECTION_FAIL = -2
    OTHER_ERROR = -3

    prev_checked_ids = []
    new_checked_ids = []

    def read_regexes(self):
        try:
            with open ( self.REGEXES_FILE, 'r') as f:
                try:
                    self.regexes = [ [ field.strip() for field in line.split(',')] for line in f.readlines() if line.strip() != '' and not line.startswith('#')]

                    # In case commas exist in the regexes...merge everything.
                    for i in range(len(self.regexes)):
                        self.regexes[i] = [','.join(self.regexes[i][:-2])] + self.regexes[i][-2:]
                except KeyboardInterrupt:
                    raise
                except:
                    Logger(self.verbose).fatal_error('Malformed regexes file. Format: regex_pattern,URL logging file, directory logging file.')

            #for regex,file,directory in self.regexes:
                #Logger (self.verbose).log ( directory+':\t'+file+':\t'+regex[:68])
            Logger (self.verbose).log ( '{:d} regex rules are refreshed.'.format(len(self.regexes)), True)

        except KeyboardInterrupt:
            raise
        except:
            Logger(self.verbose).fatal_error('{:s} not found or not acessible.'.format(self.REGEXES_FILE))


    def __init__(self):
        #self.read_regexes()
        self.kill_now = False
        self.delayfactor = 1	# dynamically adjust the delay time of retrieving each paste
        self.min_delayfactor = 0.5	# minimal acceptable delay factor preventing from being banned
        self.max_delayfactor = 1.6	# maxium acceptable delay factor for efficiency
## values used in self.conclude() stats
        self.totalpastes = 0
        self.validpastes = 0
        self.starttime = time.time()
        self.starttime_ts = get_timestamp()
        self.totalerrors = 0
## values used in debug mode to track run time stats
        self.stats = {}
        self.init_stat('get_pastes')
        self.init_stat('check_paste')

## register os signals to response to kill interruption
        signal.signal(signal.SIGINT, self.handle)
        signal.signal(signal.SIGTERM, self.handle)

    def init_stat(self,stat):
        if stat not in self.stats:
            self.stats[stat] = {}
        self.stats[stat]['total'] = 0
        self.stats[stat]['num'] = 0
        self.stats[stat]['avg'] = lambda :self.stats[stat]['total']/self.stats[stat]['num'] if self.stats[stat]['num'] != 0 else 0
    def check_stat(self,start,stat):
        if stat not in self.stats:
            return 0,0
        if start >= 0:
            now = time.time()
            self.stats[stat]['num'] += 1
            self.stats[stat]['total'] += now - start
            return now - start, (now - start - self.stats[stat]['avg']()) / self.stats[stat]['avg']()
        else:	# return avg if start==0
            return self.stats[stat]['avg']()

    def runduration(self,timestamp1, timestamp2):
        dt1 = datetime.datetime.fromtimestamp(timestamp1)
        dt2 = datetime.datetime.fromtimestamp(timestamp2)
        rd = dateutil.relativedelta.relativedelta (dt2, dt1)
        dur = '' if rd.years == 0 else '{:d} years'.format(rd.years)
        dur = dur + ('' if rd.months == 0 else ', {:d} months'.format(rd.months))
        dur = dur + ('' if rd.days == 0 else ', {:d} days'.format(rd.days))
        dur = dur + ('' if rd.hours == 0 else ', {:d} hours'.format(rd.hours))
        dur = dur + ('' if rd.minutes == 0 else ', {:d} minutes'.format(rd.minutes))
        dur = dur + ('no time' if rd.seconds == 0 else ', {:d} seconds'.format(rd.seconds))

        return dur.strip(', ')

    def handle(self, signum, frame):
        self.kill_now = True

    def conclude(self):
## stats from startup
        Logger(self.verbose).log ('Since started at {:s}, the program has run for {:s}.'.format(self.starttime_ts, self.runduration(self.starttime,time.time())), True)
        Logger(self.verbose).log ('It processed {:d} pastes, including {:d} recorded and {:d} errors.'.format(self.totalpastes, self.validpastes, self.totalerrors), True)
        Logger(self.verbose).log ('Averagely it took {:.2f}s to fetch pastes, and {:.2f}s to check a single paste.'.format(self.stats['get_pastes']['avg'](), self.stats['check_paste']['avg']()), True)

    def __del__(self):
        self.conclude()

    def get_pastes ( self ):
        Logger (self.verbose).log ( 'Getting pastes', True )
        try:
            page = PyQuery ( url = self.PASTES_URL )
        except KeyboardInterrupt:
            raise
        except:
            return self.CONNECTION_FAIL,None


        """
        There are a set of encoding issues which, coupled with some bugs in etree (such as in the Raspbian packages) can
        trigger encoding exceptions here. As a workaround, we try every possible encoding first, and even if that fails,
        we resort to a very hacky workaround whereby we manually get the page and attempt to encode it as utf-8. It's
        ugly, but it works for now.
        """
        try:
            page_html = page.html ()
        except KeyboardInterrupt:
            raise
        except:
            worked = False
            # try utf8 first
            try:
                f = urllib.request.urlopen(Crawler.PASTES_URL)
                page_html = PyQuery(str(f.read()).encode('utf8')).html()
                f.close()
                worked = True
            except KeyboardInterrupt:
                raise
            except:
                pass
            if not worked:
                Logger(self.verbose).warn('Using UTF-8 to get_pastes does not work, try other encodings...')
                for enc in all_python_encodings():
                    try:
                        page_html = page.html(encoding=enc)
                        worked = True
                        break
                    except KeyboardInterrupt:
                        raise
                    except:
                        return self.OTHER_ERROR, None

        if re.match ( r'Pastebin\.com - Access Denied Warning', page_html, re.IGNORECASE ) or 'blocked your IP' in page_html or 'unatural browsing behavior' in page_html:
            return self.ACCESS_DENIED,None
        else:
            return self.OK,page('.maintable img').next('a')

    def check_paste ( self, paste_id ):
        self.totalpastes += 1
        paste_url = self.PASTEBIN_URL + (paste_id if paste_id[0] == '/' else '/' + paste_id)
        try:
            #paste_txt = PyQuery ( url = paste_url )('#paste_code').text()
            paste_txt = urllib.request.urlopen(paste_url).read().decode('utf-8').strip()

            for regex,file,directory in self.regexes:
                if self.kill_now == True:
                    exit()
                r = re.search ( regex, paste_txt, re.IGNORECASE )
                if r:
                    Logger ().match( 'Found a matching paste: ' + paste_url.rsplit('/')[-1] + ' (' + file + '): '+ r[0] )
                    #self.save_result ( paste_url,paste_id,'data/'+file,'data/'+directory )
                    self.save_result( paste_id=paste_id,paste_txt=paste_txt,file='data/'+file,directory='data/'+directory )
                    return True
            #Logger (self.verbose).log ( 'Not matching paste: ' + paste_url )
        except KeyboardInterrupt:
            raise
        except Exception as inst:
            self.totalerrors += 1
            if str(inst) == 'HTTP Error 404: Not Found':
                Logger ().warn ( '404 Error reading paste {:s}.'.format(paste_id))	# likely being removed
            else:
                Logger ().warn ( 'Error reading paste {:s} (probably encoding issue or regex issue), error is {:s}.'.format(paste_id,str(inst)))
        return False

    def save_result ( self, paste_id, paste_txt, file, directory ):
        self.validpastes += 1
        paste_url = self.PASTESRAW_URL + (paste_id if paste_id[0] == '/' else '/' + paste_id)
        fn,ext = os.path.splitext(os.path.split(file)[1])
        timestamp = get_timestamp()
        with open ( file, 'a' ) as matching:
            matching.write ( fn + '-' + timestamp + '-' + paste_url + '\n' )

        try:
            os.mkdir(directory)
        except KeyboardInterrupt:
            raise
        except:
            pass

        with open( directory + '/' + fn + '_' + timestamp.replace('/','_').replace(':','_').replace(' ','__') + '_' + paste_id.replace('/','') + '.txt', mode='w' ) as paste:
            if paste_txt == '':
                paste_txt = urllib.request.urlopen(paste_url).read().decode('utf-8').strip()
                #paste_txt = PyQuery(url=paste_url)('#paste_code').text()
            paste.write(paste_txt + '\n')


    def start ( self, refresh_time, delay, ban_wait, flush_after_x_refreshes, connection_timeout, verbose ):
        count = 0
        self.verbose = verbose
        while True:
            if self.kill_now == True:
                exit()

            self.conclude()
            start = time.time()
            status,pastes = self.get_pastes ()
            tooktime,times = self.check_stat(start,'get_pastes')
            if times > 10:
                Logger(self.verbose).warn('It took {:.2f}s to get_pastes, which is {:.2f} times of average'.format(tooktime,times))

            start_time = time.time()
            if status == self.OK:
                delayed = 0
                currpaste = 0
                totaldelayed = 0
                chkedpaste = 0
                numofpastes = len(pastes) or 0
                Logger(self.verbose).log('Retreived {:d} pastes, will process using delay factor of {:.2f} ...'.format(numofpastes,self.delayfactor),True)
                self.read_regexes()
                for paste in pastes:
                    currpaste += 1
                    paste_id = PyQuery ( paste ).attr('href')
                    self.new_checked_ids.append ( paste_id )
                    if paste_id not in self.prev_checked_ids:
                        chkedpaste += 1
                        start = time.time()
                        #Logger(self.verbose).log('Start processing paste {:s}'.format(paste_id))
                        self.check_paste ( paste_id )
                        tooktime,times = self.check_stat(start,'check_paste')
                        if times >= 20:
                            Logger(self.verbose).error('{:s} might be a giant paste that took {:.2f}s to check, it is {:.2f} times of average'.format(paste_id,tooktime,times))
                        elif times > 10:
                            Logger(self.verbose).warn('{:s} took {:.2f}s to check, which is {:.2f} times of average'.format(paste_id,tooktime,times))
                        delaytime = delay*random.uniform(0.6,1.1)*self.delayfactor
                        totaldelayed += delaytime
                        Logger(self.verbose).log('Paste {:02d}/{:02d} done; Waiting {:.2f} seconds for next paste ...'.format(currpaste,numofpastes,delaytime))
                        if currpaste < numofpastes:
                            time.sleep(delaytime)

                    if currpaste == numofpastes:
                        Logger(self.verbose).log('Average/Total waiting time is {:.2f}s/{:.2f}m for the pastes'.format(totaldelayed/numofpastes,totaldelayed/60), True)
                        if chkedpaste < numofpastes:
                            Logger(self.verbose).log('Good job! You caught up all new pastes since last update! {:d} pastes are already checked'.format(numofpastes-chkedpaste), True)
                            self.delayfactor = self.max_delayfactor if self.delayfactor >= self.max_delayfactor else (self.delayfactor + 0.04*fabs(numofpastes-chkedpaste))	# slow down a little bit
                        else:
                            self.delayfactor = self.min_delayfactor if self.delayfactor <= self.min_delayfactor else (self.delayfactor - 0.24)	# speed up a little bit
                    count += 1
                    if self.kill_now == True:	# caught kill signal
                        exit()

                if count == flush_after_x_refreshes:
                    self.prev_checked_ids = self.new_checked_ids
                    count = 0
                else:
                    self.prev_checked_ids += self.new_checked_ids
                self.new_checked_ids = []

                elapsed_time = time.time() - start_time
                sleep_time = ceil(max(0,(refresh_time*random.gauss(1,0.2) - elapsed_time)))
                if sleep_time > 0:
                    Logger(self.verbose).log('Waiting {:d} seconds to refresh...'.format(sleep_time), True)
                    time.sleep ( sleep_time )
                else:
                    Logger(self.verbose).log('refresh_time={:d}, elapsed_time={:.2f}, sleep_time={:.2f}'.format(refresh_time,elapsed_time,sleep_time), False)
            elif status == self.ACCESS_DENIED:
                self.totalerrors += 1
                delayed += 1
                self.delayfactor = 1
                Logger ().warn ( 'Damn! It looks like you have been banned (probably temporarily)' )
                for n in range ( 0, ceil(ban_wait*random.gauss(1+delayed*0.2,0.2)) ):
                    Logger (self.verbose).log ( 'Please wait ' + str ( ban_wait - n ) + ' more minute' + ( 's' if ( ban_wait - n ) > 1 else '' ) )
                    time.sleep ( 60 )
            elif status == self.CONNECTION_FAIL:
                self.totalerrors += 1
                Logger().error ( 'Connection down. Waiting {:d} seconds and trying again'.format(connection_timeout) )
                time.sleep(connection_timeout)
            elif status == self.OTHER_ERROR:
                self.totalerrors += 1
                Logger().error('Unknown error. Maybe an encoding problem? Trying again.'.format(connection_timeout))
                time.sleep(1)

def parse_input():
    parser = OptionParser()
    parser.add_option('-r', '--refresh-time', help='Set the refresh time (default: 200)', dest='refresh_time', type='int', default=200)
    parser.add_option('-d', '--delay-time', help='Set the delay time (default: 5)', dest='delay', type='float', default=5)
    parser.add_option('-b', '--ban-wait-time', help='Set the ban wait time (default: 30)', dest='ban_wait', type='int', default=30)
    parser.add_option('-f', '--flush-after-x-refreshes', help='Set the number of refreshes after which memory is flushed (default: 100)', dest='flush_after_x_refreshes', type='int', default=100)
    parser.add_option('-c', '--connection-timeout', help='Set the connection timeout waiting time (default: 60)', dest='connection_timeout', type='float', default=60)
    parser.add_option('-V', '--verbose', help='enable debug mode for verbose output',dest='verbose', action="store_true")
    (options, args) = parser.parse_args()
    return options.refresh_time, options.delay, options.ban_wait, options.flush_after_x_refreshes, options.connection_timeout, options.verbose


if __name__ == "__main__":
    
    try:
#        refresh_time, delay, ban_wait, flush_after_x_refreshes, connection_timeout, verbose = parse_input()
        Crawler ().start (*parse_input())
#        Crawler ().start (refresh_time=refresh_time,delay=delay,ban_wait=ban_wait,flush_after_x_refreshes=flush_after_x_refreshes,connection_timeout=connection_timeout,verbose=verbose)
    except KeyboardInterrupt:
        Logger (self.verbose).log ( 'Bye! Hope you found what you were looking for :)', True )
