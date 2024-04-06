

from mqtt_as import MQTTClient
from mqtt_local import config
import uasyncio as asyncio
import dht, machine
from machine import Timer
from collections import OrderedDict
import json
import ubinascii
import btree
import time
import settings

CLIENT_ID = ubinascii.hexlify(machine.unique_id()).decode('utf-8')

# configuracion de pines... Sensor, rele, led
d = dht.DHT22(machine.Pin(25))
pin_rele = machine.Pin(12, machine.Pin.OUT)
pin_led = machine.Pin(2, machine.Pin.OUT)

global periodo
global bandtransmitir
global bandestello

bandestello = False
setpoint=40
#modo automatico = TRUE, MANUAL = FALSE
modo=False
#periodo en ms
periodo=10000
#rele empieza apagado, es activo en bajo
rele_estado=True
datos={}
# bandera para transmitir
bandtransmitir = False


## base de datos
try:
    f = open("mydb", "r+b")
except OSError:
    f = open("mydb", "w+b")

db = btree.open(f)

db[b"Setpoint"] = str(setpoint)
db[b"Modo"] = str(modo)
db[b"Periodo"] = str(periodo)
db[b"Rele Estado"] = str(rele_estado)

db.flush()


def transmitir(pin):
    global bandtransmitir
    
    print("Transmite !")
    bandtransmitir = True

timer_publicar=Timer(0)
timer_publicar.init(period=periodo, mode=Timer.PERIODIC, callback=transmitir)


def sub_cb(topic, msg, retained):
    global periodo
    global bandestello
    global modo
    global setpoint
    global periodo

    print('Topic = {} -> Valor = {}'.format(topic.decode(), msg.decode()))
    mensaje = str(msg.decode())
    if topic.decode() == f"{CLIENT_ID}/periodo":
            periodo = int(mensaje)
            timer_publicar=Timer(0)
            timer_publicar.init(period=periodo, mode=Timer.PERIODIC, callback=transmitir)
        
    if topic.decode() == f"{CLIENT_ID}/setpoint":
        setpoint = int(mensaje)

    if topic.decode() == f"{CLIENT_ID}/modo":
        if mensaje == "auto":
            modo = True
        elif mensaje == "manual":
            modo = False
        print(f"modo = {mensaje}")

    if topic.decode() == f"{CLIENT_ID}/rele":
        if mensaje == "on":
            rele_estado = False
            db[b"Rele Estado"] = str(rele_estado)
        elif mensaje == "off":
            rele_estado = True
            db[b"Rele Estado"] = str(rele_estado)

    if topic.decode() == f"{CLIENT_ID}/destello":
        if mensaje == "on":
            bandestello = True

async def wifi_han(state):
    print('Wifi is ', 'up' if state else 'down')
    await asyncio.sleep(1)

async def conn_han(client):
    await client.subscribe(f'{CLIENT_ID}/temperatura', 1)  
    await client.subscribe(f'{CLIENT_ID}/humedad', 1)  
    await client.subscribe(f'{CLIENT_ID}/rele', 1)  
    await client.subscribe(f'{CLIENT_ID}/modo', 1) 
    await client.subscribe(f'{CLIENT_ID}/periodo', 1)
    await client.subscribe(f'{CLIENT_ID}/destello', 1) 
    await client.subscribe(f'{CLIENT_ID}/setpoint', 1) 

async def main(client):
    global bandtransmitir
    global modo
    global setpoint
    global periodo

    await client.connect()
    await asyncio.sleep(2)  # Give broker time
    # DEBUG
    bandtransmitir = True #False
    while True:
        try:
            #d.measure()
            temperatura=0#d.temperature()
            humedad=100#d.humidity()
            
            datos=json.dumps(OrderedDict([
                ('temperatura',temperatura),
                ('humedad',humedad),
                ('modo', modo),
                ('periodo', periodo),
                ('setpoint', setpoint)
                ]))
            print(datos)
            db[b"Temperatura"] = str(temperatura)
            db[b"Humedad"] = str(humedad)
        except OSError as e:
            print("sin sensor temperatura")
        if modo == True:
            if temperatura>setpoint:
                rele_estado=False
                pin_rele.value(0)
                db[b"Rele Estado"] = str(rele_estado)
            else:
                rele_estado=True
                pin_rele.value(1)
                db[b"Rele Estado"] = str(rele_estado)
        if bandtransmitir:
            print(f"publicando en {CLIENT_ID}")
            await client.publish(CLIENT_ID ,datos, qos = 1)
            bandtransmitir=False
    
        
        db.flush()
        await asyncio.sleep(2)  # Broker is slow


async def destello():
    global bandestello
    
    if bandestello:
        print("DESTELLO !!!")
        pin_led.value(True)
        await asyncio.sleep(1)
        pin_led.value(False)
        await asyncio.sleep(1)
        pin_led.value(True)
        await asyncio.sleep(1)
        pin_led.value(False)
        await asyncio.sleep(1)
        bandestello = False


# Define configuration
config['subs_cb'] = sub_cb
config['connect_coro'] = conn_han
config['wifi_coro'] = wifi_han
config['ssl'] = True

# Set up client
MQTTClient.DEBUG = True  # Optional
client = MQTTClient(config)

try:
    asyncio.run(main(client))
finally:
    client.close()
    asyncio.new_event_loop()

