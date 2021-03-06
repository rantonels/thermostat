
#imports for thermometer reading
import os
import glob
import time
#imports for gmail reading
import imaplib
import email
#import for Telegram API
import sys
import pprint
import telepot

import requests

#import library for logging
import logging
logging.basicConfig(filename='termostato.log', level=logging.WARNING)

persone_della_casa = 4
persona=['Ferruccio','Claudia','Riccardo','Lorenzo']
persona_at_home=[True, True, True, True]
EMAIL_ID='MaggiordomoBot@gmail.com'
EMAIL_PASSWD='cldbzz00'

###################### gestisce i comandi inviati al Telegram Bot
def handle(msg):
    global persona_at_home
    global last_report, report_interval     #parametri per il monitoraggio su file delle temperature
    global heating_status, heating_standby  #stato di accensione dei termosifoni
    global who_is_at_home, how_many_at_home

    logging.debug('inizio la gestione di handle')
    msg_type, chat_type, chat_id = telepot.glance(msg)

    # ignore non-text message
    if msg_type != 'text':
        return

    command = msg['text'].strip().lower()
    CurTemp = read_temp()
    
    logging.debug('elaboro il comando '+command)
    
    if command == '/now':
        bot.sendMessage(chat_id, "La temperatura misurata e' di "+str("%0.1f" % CurTemp)+" C, Padrone")
    elif command == '/5m':
        bot.sendMessage(chat_id, "Avvio il monitoraggio ogni 5 minuti, Padrone")
        last_report = time.time()
        report_interval = 300    # report every 60 seconds
    elif command == '/1h':
        bot.sendMessage(chat_id, "Avvio il monitoraggio ogni ora, Padrone")
        last_report = time.time()
        report_interval = 3600  # report every 3600 seconds
    elif command == '/annulla':
        last_report = None
        report_interval = None  # clear periodic reporting
        bot.sendMessage(chat_id, "Certamente, Padrone")
    elif command == '/ho_freddo':
        if heating_status:
            bot.sendMessage(chat_id, "Sto facendo del mio meglio, Padrone")
        else:
            GPIO.output(17, 1) # sets port 0 to 1 (3.3V, on) per accendere i termosifoni
            heating_status = True #print "HEATING ON "+localtime+"\n"
            f = open("heating_status","w")
            f.write('ON')
            f.close()  #chiude il file dei dati e lo salva
            bot.sendMessage(chat_id, "Accendo il riscaldamento, Padrone")
    elif command == '/ho_caldo':
        if heating_status:
            GPIO.output(17, 0) # sets port 0 to 0 (3.3V, off) per spengere i termosifoni
            heating_status = False #print "HEATING OFF "+localtime+"\n"
            f = open("heating_status","w")
            f.write('OFF')
            f.close()  #chiude il file dei dati e lo salva
            bot.sendMessage(chat_id, "Spengo il riscaldamento, Padrone")
        else:      
            bot.sendMessage(chat_id, "Dovresti aprire le finestre, Padrone")
    elif command == '/casa':
        who_is_at_home=""
        how_many_at_home=0
        for who_at_home in range(persone_della_casa):
            if persona_at_home[who_at_home]:
                who_is_at_home+=persona[who_at_home]+" "
                how_many_at_home+=1
        if how_many_at_home != 0:
            if how_many_at_home == 1:
                bot.sendMessage(chat_id, who_is_at_home+"e' a casa")
            else:
                bot.sendMessage(chat_id, who_is_at_home+"sono a casa")
        else:
            bot.sendMessage(chat_id, "Sono solo a casa, Padrone")
    elif command == '/help':
        # send message for help
        bot.sendMessage(chat_id, "Sono il Maggiordomo e custodisco la casa. Attendo i suoi comandi Padrone per eseguirli prontamente e rendere la sua vita piacevole e felice.\n/now - mostra la temperatura\n/ho_freddo - accende il riscaldamento\n/ho_caldo - spegne il riscaldamento\n/casa - chi e' a casa?")
        if heating_status:
            bot.sendMessage(chat_id, "Riscaldamento attivato")
        else:
            bot.sendMessage(chat_id, "Riscaldamento disattivato")

    else:
        bot.sendMessage(chat_id, "Puoi ripetere, Padrone? I miei circuiti sono un po' arrugginiti")



############ legge da file il token del Telegram Bot e della chat id

tokenpath = os.path.dirname(os.path.realpath(__file__)) + "/token"
chatidpath = os.path.dirname(os.path.realpath(__file__)) + "/chatid"


try:
    tokenFile = open(tokenpath,'r')
    TOKEN = tokenFile.read().strip()
    tokenFile.close()
except IOError: 
    logging.error("Non ho trovato il file di token. E' necessario creare un file 'token' con la token telegram per il bot. In ogni caso questo file NON deve essere tracciato da git - viene ignorato perche' menzionato nel .gitignore.")
    exit()

logging.info("caricata token.")
        
try:
    chatidFile = open(chatidpath,'r')
    CHAT_ID = chatidFile.read().strip()
    chatidFile.close()
except IOError:
    logging.error("Non ho trovato il file di chatId. E' necessario creare un file 'chatid' con la chatid telegram per il bot")
    # In ogni caso questo file NON deve essere tracciato da git - viene ignorato perche' menzionato nel .gitignore.")

logging.info("caricata chatId.")
    
    #-94452612 # magic number: chat_id del gruppo termostato antonelli
        

# variables for periodic reporting
last_report = time.time()
report_interval = 3600  # report every 3600 seconds (1 hour) as a default

# variable for heating status
heating_status = False
heating_standby = False


################# gestione della interfaccia di GPIO   
# wiringpi numbers  
import RPi.GPIO as GPIO
##import wiringpi2 as wiringpi
##wiringpi.wiringPiSetup()
##wiringpi.pinMode(0, 1) # sets WP pin 0 to output
GPIO.setmode(GPIO.BCM)
GPIO.setup(17,GPIO.OUT)

#Find temperature from thermometer
os.system('modprobe w1-gpio')
os.system('modprobe w1-therm')

base_dir = '/sys/bus/w1/devices/'
device_folder = glob.glob(base_dir + '28*')[0]
device_file = device_folder + '/w1_slave'

def read_temp_raw():
    f = open(device_file, 'r')
    lines = f.readlines()
    f.close()
    return lines

def read_temp():
    lines = read_temp_raw()
    while lines[0].strip()[-3:] != 'YES':
        time.sleep(0.2)
        lines = read_temp_raw()
    equals_pos = lines[1].find('t=')
    if equals_pos != -1:
        temp_string = lines[1][equals_pos+2:]
        temp_c = float(temp_string) / 1000.0
        temp_f = temp_c * 9.0 / 5.0 + 32.0
        return temp_c #, temp_f

##################### funzione per la gestione dei messaggi di presence
def set_presence(presence_msg):
    global persona_at_home, who_is_at_home, how_many_at_home
    global heating_status, heating_standby
    
    logging.debug('gestisco il messaggio di presence '+presence_msg)
    
    if len(presence_msg) !=0:
        words = presence_msg.split(' ', 2)
        nome = words[0]
        status = words[1]
        try:
            IFTTTtime = words[2]
            logging.info("IFTTTtime "+IFTTTtime)
            orario = time.strptime(IFTTTtime, "%B %d, %Y at %I:%M%p")
            logging.info("orario letto da mail "+time.asctime(orario))
        except:
            e = sys.exc_info()[0]
            logging.error( "<p>Error: %s</p>" % e )
            orario = time.localtime(now)
        # scrive la info di presence su file

        localtime = time.asctime( orario )
        ora_minuti = time.strftime("%H:%M", orario)
        filepresence = open("filepresence","a")  #apre il file dei dati in append mode, se il file non esiste lo crea
        filepresence.write(presence_msg+" "+localtime+"\n")  #scrive la info di presence ed il timestam sul file
        filepresence.close()  #chiude il file dei dati e lo salva

        for n in range(persone_della_casa):
            if nome == persona[n]:
                if status == 'IN':
                    if persona_at_home[n] == False:
                        persona_at_home[n] = True
                        bot.sendMessage(CHAT_ID, "Benvenuto a casa "+nome+"\nSono le "+ora_minuti)
                        f = open(persona[n]+"_at_home","w")  #apre il file dei dati in write mode, se il file non esiste lo crea
                        f.write("IN")  #scrive la info di presence sul file
                        f.close()  #chiude il file dei dati e lo salva
                elif persona_at_home[n]:
                    persona_at_home[n] = False
                    bot.sendMessage(CHAT_ID, "Arrivederci a presto "+nome+"\nSono le "+ora_minuti)
                    f = open(persona[n]+"_at_home","w")  #apre il file dei dati in write mode, se il file non esiste lo crea
                    f.write("OUT")  #scrive la info di presence sul file
                    f.close()  #chiude il file dei dati e lo salva
        else:
            bot.sendMessage(CHAT_ID, "Padrone verifica se ci sono sconosciuti in casa!")
    # calcola chi e' a casa
    who_is_at_home=""
    how_many_at_home=0
    n=0
    for n in range(persone_della_casa):
        if persona_at_home[n]:
            who_is_at_home+=persona[n]
            how_many_at_home+=1
    if how_many_at_home == 0: #nessuno in casa
        if heating_standby == False:  #standby termosifoni non attivo
            heating_standby = True
            f = open("heating_standby","w")
            f.write('ON')
            f.close()  #chiude il file dei dati e lo salva
            if heating_status: #se termosifoni attivi
                GPIO.output(17, 0) # spenge i termosifoni
                bot.sendMessage(CHAT_ID, "Ho messo in stand by il riscaldamento in attesa che rientri qualcuno a casa")
    else: #almeno una persona in casa
        if heating_standby: #se standby attivo
            heating_standby = False
            f = open("heating_standby","w")
            f.write('OFF')
            f.close()  #chiude il file dei dati e lo salva
            if heating_status: #se termosifoni attivi prima dello standby
                GPIO.output(17, 1) # riaccende i termosifoni
                bot.sendMessage(CHAT_ID, "Ho riavviato il riscaldamento per il tuo confort, Padrone")
    #return set_presence            

##### connette o riconnette alla mail ###########
def connect(retries=5, delay=3):
    while True:
        try:
            imap_host = 'imap.gmail.com'
            mail = imaplib.IMAP4_SSL(imap_host)
            mail.login(EMAIL_ID,EMAIL_PASSWD)
            return mail
        except imaplib.IMAP4_SSL.abort:
            if retries > 0:
                retries -= 1
                time.sleep(delay)
            else:
                raise
#################################################

##################### inizio gestione presence via email ################
#connect to gmail
def read_gmail():
    global mail
    logging.debug('leggo mail')
    
    #mail = imaplib.IMAP4_SSL('imap.gmail.com')
    #mail.login('MaggiordomoBot@gmail.com','cldbzz00') #login e password da mettere su file successivamente
    try:
        mail.select('inbox')
        mail.list()
        # Any Emails? 
        n=0
        (retcode, messages) = mail.search(None, '(UNSEEN)')
        if retcode == 'OK':
            for num in messages[0].split() :
                logging.info('Processing new emails...')
                n=n+1
                typ, data = mail.fetch(num,'(RFC822)')
                for response_part in data:
                    if isinstance(response_part, tuple):
                        original = email.message_from_string(response_part[1])
                        subject_text=str(original['Subject'])
                        set_presence(subject_text) #richiama la funzione per la gestisce della presence
                        typ, data = mail.store(num,'+FLAGS','\\Seen') #segna la mail come letta
                logging.info("Ho gestito "+str(n)+" messaggi di presence")
    except:
        logging.debug('Errore nella lettura della mail')
        mail = connect()

############################### fine gestione presence via email #######################

############################ TEST Internet connection #############
import socket
REMOTE_SERVER = "www.google.com"
def is_connected():
    now = time.time()
    localtime = time.asctime( time.localtime(now) )
    try:
        # see if we can resolve the host name -- tells us if there is
        # a DNS listening
        host = socket.gethostbyname(REMOTE_SERVER)
        # connect to the host -- tells us if the host is actually
        # reachable
        s = socket.create_connection((host, 80), 2)
        return True
    except Exception as e:
        logging.exception("www.google.com not reachable at "+str(localtime))
        pass
    return False
######### fine test internet connection

#inizio programma

for n in range(persone_della_casa):
    try:
        f = open(persona[n]+"_at_home","r")  #apre il file dei dati in read mode
        pres=f.read().strip()   #legge la info di presence sul file
        f.close()  #chiude il file dei dati e lo salva
        if pres == "IN":
            persona_at_home[n] = True
        else:
            persona_at_home[n] = False
    except IOError:
        persona_at_home[n] = False  #se il file non e' presente imposto la presence a False

try:
    f = open("heating_status","r")  #apre il file dei dati in read mode
    h_status=f.read().strip()   #legge la info di presence sul file
    f.close()  #chiude il file dei dati e lo salva
    if h_status == "ON":
        heating_status = True
    else:
        heating_status = False
except IOError:
    heating_status = False  #se il file non e' presente imposto la presence a False

try:
    f = open("heating_standby","r")  #apre il file dei dati in read mode
    hby_status=f.read().strip()   #legge la info di presence sul file
    f.close()  #chiude il file dei dati e lo salva
    if hby_status == "ON":
        heating_standby = True
    else:
        heating_standby = False
except IOError:
    heating_standby = False  #se il file non e' presente imposto la presence a False


bot = telepot.Bot(TOKEN)
bot.notifyOnMessage(handle)
logging.info("Listening ...")

show_keyboard = {'keyboard': [['/now','/casa'], ['/ho_caldo','/ho_freddo']]} #tastiera personalizzata
bot.sendMessage(CHAT_ID, 'Mi sono appena svegliato, Padrone')

if heating_status and not heating_standby:
    GPIO.output(17, 1) # sets port 0 to 0 (3.3V, off) per spengere i termosifoni
    bot.sendMessage(CHAT_ID, "Rispristino il riscaldamento, Padrone")

bot.sendMessage(CHAT_ID, 'Come ti posso aiutare?', reply_markup=show_keyboard)

mail = connect() #apre la casella di posta

while True:
    #try:
        # Is it time to report again?
        now = time.time()
        localtime = time.asctime( time.localtime(now) )
        if report_interval is not None and last_report is not None and now - last_report >= report_interval:
            CurTemp = read_temp()
            #apre il file dei dati in append mode, se il file non esiste lo crea
            filedati = open("filedati","a")
            #scrive la temperatura coreente ed il timestam sul file
            filedati.write(str(CurTemp)+"@"+localtime+"\n")
            #chiude il file dei dati e lo salva
            filedati.close()
        
            last_report = now
        # verifica se ci sono nuovi aggiornamenti sulla presence (via email)
        if is_connected():
            read_gmail()
        time.sleep(60)
    #except Exception:
    #    logging.exception("C'e' stato un errore del programma termostato")
    
