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
pin_rele.value(1)
pin_led = machine.Pin(2, machine.Pin.OUT)
pin_led.value(1)


setpoint=40
#modo automatico = TRUE, MANUAL = FALSE
modo=False
#periodo en segundos
periodo=3.3
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

#abro la base de datos
db = btree.open(f)


#guardo los datos iniciales
db[b"Setpoint"] = str(setpoint)
db[b"Modo"] = str(modo)
db[b"Periodo"] = str(periodo)
db[b"Rele Estado"] = str(rele_estado)

#limpio el caché de la base de datos
db.flush()

#funcion para transmitir el json
async def transmitir(pin):  
    while True:
        print(f"publicando en {CLIENT_ID}")
        await client.publish(CLIENT_ID, datos, qos = 1)
        await asyncio.sleep(float(db[b"Periodo"]))


#funcion para recibir mensajes de los distintos topicos guardando los mensajes en la base de datos
def sub_cb(topic, msg, retained):
    topicodecodificado = topic.decode()
    mensajedecodificado = msg.decode()
    print('Topic = {} -> Valor = {}'.format(topicodecodificado, mensajedecodificado))

    if topicodecodificado == f"{CLIENT_ID}/periodo":
        db[b"Periodo"] = mensajedecodificado
        
    if topicodecodificado == f"{CLIENT_ID}/setpoint":
        db[b"Setpoint"] = mensajedecodificado

    if topicodecodificado == f"{CLIENT_ID}/modo":
        if mensajedecodificado == "1" or mensajedecodificado == "0":
            db[b"Modo"] = mensajedecodificado
        else:
            print("No existe ese modo!")

    if topicodecodificado == f"{CLIENT_ID}/rele":
        if mensajedecodificado == "on":
            rele_estado = False
            db[b"Rele Estado"] = str(rele_estado)
        elif mensajedecodificado == "off":
            rele_estado = True
            db[b"Rele Estado"] = str(rele_estado)

    if topicodecodificado == f"{CLIENT_ID}/destello":
        if mensajedecodificado == "on":
            asyncio.run(destello())



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
    await client.connect()
    await asyncio.sleep(2)  # Give broker time


    while True:
        try:
            d.measure()
            temperatura=d.temperature()
            humedad=d.humidity()
            
            datos=json.dumps(OrderedDict([
                ('temperatura',temperatura),
                ('humedad',humedad),
                ('modo', bool(db.get("Modo"))),
                ('periodo', float(db.get("Periodo"))),
                ('setpoint', float(db.get("Setpoint")))
                ]))
            print(datos)
            db[b"Temperatura"] = str(temperatura)
            db[b"Humedad"] = str(humedad)
        except OSError as e:
            print("sin sensor temperatura")
        if bool(db.get("Modo")) == True:
            if temperatura>int(db.get("Setpoint")):
                rele_estado=False
                pin_rele.value(0)
                db[b"Rele Estado"] = str(rele_estado)
            else:
                rele_estado=True
                pin_rele.value(1)
                db[b"Rele Estado"] = str(rele_estado)
        
        db.flush()
        await asyncio.sleep(2)  # Broker is slow


async def destello():
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



async def task(client):
    await asyncio.gather(transmitir(), main(client))


# Define configuration
config['subs_cb'] = sub_cb
config['connect_coro'] = conn_han
config['wifi_coro'] = wifi_han
config['ssl'] = True

# Set up client
MQTTClient.DEBUG = True  # Optional
client = MQTTClient(config)

try:
    asyncio.run(task(client))
finally:
    #cierro base de datos
    db.close()
    f.close()
    client.close()
    asyncio.new_event_loop()
