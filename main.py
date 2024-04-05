

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


setpoint=40
#modo automatico = TRUE, MANUAL = FALSE
modo=False
#periodo en ms
periodo=3000
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
    bandtransmitir = True

timer_publicar=Timer(0)
timer_publicar.init(period=periodo, mode=Timer.PERIODIC, callback=transmitir)


def sub_cb(topic, msg, retained):
    print('Topic = {} -> Valor = {}'.format(topic.decode(), msg.decode()))
    if topic.decode() == f"{CLIENT_ID}/periodo":
            periodo = int(msg)
            timer_publicar=Timer(0)
            timer_publicar.init(period=periodo, mode=Timer.PERIODIC, callback=transmitir)
        
    if topic.decode() == f"{CLIENT_ID}/setpoint":
        setpoint = int(msg)

    if topic.decode() == f"{CLIENT_ID}/modo":
        if msg == "auto":
            modo = True
        elif msg == "manual":
            modo = False
        print(f"modo = {msg}")

    if topic.decode() == f"{CLIENT_ID}/rele":
        if msg == "on":
            rele_estado = False
            db[b"Rele Estado"] = str(rele_estado)
        elif msg == "off":
            rele_estado = True
            db[b"Rele Estado"] = str(rele_estado)

    if topic.decode() == f"{CLIENT_ID}/destello":
        if msg == "on":
            destello()

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

async def main(client):
    await client.connect()
    await asyncio.sleep(2)  # Give broker time
    bandtransmitir = False
    while True:
        try:
            d.measure()
            temperatura=d.temperature()
            humedad=d.humidity()
            
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
            await client.publish(f"CLIENT_ID",datos, qos = 1)
            bandtransmitir=False
    
        
        db.flush()
        await asyncio.sleep(180)  # Broker is slow


async def destello():
    pin_led.value(True)
    await asyncio.sleep(200)
    pin_led.value(False)
    await asyncio.sleep(200)


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

