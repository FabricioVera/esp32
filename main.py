# (C) Copyright Peter Hinch 2017-2019.
# Released under the MIT licence.

# This demo publishes to topic "result" and also subscribes to that topic.
# This demonstrates bidirectional TLS communication.
# You can also run the following on a PC to verify:
# mosquitto_sub -h test.mosquitto.org -t result
# To get mosquitto_sub to use a secure connection use this, offered by @gmrza:
# mosquitto_sub -h <my local mosquitto server> -t result -u <username> -P <password> -p 8883

# Public brokers https://github.com/mqtt/mqtt.github.io/wiki/public_brokers

# red LED: ON == WiFi fail
# green LED heartbeat: demonstrates scheduler is running.

from mqtt_as import MQTTClient
from mqtt_local import config
import uasyncio as asyncio
import dht, machine, json
from collections import OrderedDict
import ubinascii
import btree
import time
import settings


CLIENT_ID=ubinascii.hexlify(machine.unique_id()).decode('utf-8')

# configuracion de pines... Sensor, rele, led
d = dht.DHT22(machine.Pin(13))
pin_rele = machine.Pin(12, machine.Pin.OUT)
pin_rele.value(1)
pin_led = machine.Pin(2, machine.Pin.OUT)
pin_led.value(0)

parametros={
    'setpoint':26.5,
    'periodo':3,
    'modo':True,
    'rele':True
    }

datos={}


#funcion para transmitir el json
async def transmitir_estado_led():  
    print(f"publicando en {CLIENT_ID}/estado")
    valor_led=str(bool(pin_led.value())).lower()
    await client.publish(f"sensores_remotos/{CLIENT_ID}/estado", valor_led, qos = 1)



def sub_cb(topic, msg, retained):
    topicodecodificado = topic.decode()
    mensajedecodificado = msg.decode()
    print('Topic = {} -> Valor = {}'.format(topicodecodificado, mensajedecodificado))

    if topicodecodificado == f"sensores_remotos/{CLIENT_ID}/periodo":
        print("mensaje deco:" + mensajedecodificado)
        parametros["periodo"] = int(mensajedecodificado)
        escribir_db()
        
    if topicodecodificado == f"sensores_remotos/{CLIENT_ID}/setpoint":
        parametros["setpoint"] = int(mensajedecodificado)
        escribir_db()

    if topicodecodificado == f"sensores_remotos/{CLIENT_ID}/modo":
        if mensajedecodificado == "1" or mensajedecodificado == "0":
            parametros["modo"] = bool(mensajedecodificado)
            escribir_db()
        else:
            print("No existe ese modo!")

    if topicodecodificado == f"sensores_remotos/{CLIENT_ID}/rele":
        if mensajedecodificado == "on":
            parametros["rele"] = False
            pin_rele.value(0)
            escribir_db()
        elif mensajedecodificado == "off":
            parametros["rele"] = True
            pin_rele.value(1)
            escribir_db()

    if topicodecodificado == f"sensores_remotos/{CLIENT_ID}/destello":
        if mensajedecodificado == "on":
            asyncio.create_task(destello())

    if topicodecodificado == f"sensores_remotos/{CLIENT_ID}/orden":
        print("mensaje deco:" + mensajedecodificado)
        if mensajedecodificado=='true':
            print("encendiendo LED")
            pin_led.value(1)
        else:
            print("apagando LED")
            pin_led.value(0)
        asyncio.create_task(transmitir_estado_led())
        

async def wifi_han(state):
    print('Wifi is ', 'up' if state else 'down')
    await asyncio.sleep(1)

# If you connect with clean_session True, must re-subscribe (MQTT spec 3.1.2.4)
async def conn_han(client):
    await client.subscribe(f'sensores_remotos/{CLIENT_ID}/temperatura', 1)  
    await client.subscribe(f'sensores_remotos/{CLIENT_ID}/humedad', 1)  
    await client.subscribe(f'sensores_remotos/{CLIENT_ID}/rele', 1)  
    await client.subscribe(f'sensores_remotos/{CLIENT_ID}/modo', 1) 
    await client.subscribe(f'sensores_remotos/{CLIENT_ID}/periodo', 1)
    await client.subscribe(f'sensores_remotos/{CLIENT_ID}/destello', 1) 
    await client.subscribe(f'sensores_remotos/{CLIENT_ID}/setpoint', 1) 
    await client.subscribe(f'sensores_remotos/{CLIENT_ID}/orden', 1) 

async def main(client):
    await client.connect()
    await asyncio.sleep(2)  # Give broker time
    escribir_db()

    while True:
        try:
            d.measure()
            try:
                temperatura=d.temperature()
                try:
                    humedad=d.humidity()
                    datos=json.dumps(OrderedDict([
                        ('temperatura',temperatura),
                        ('humedad',humedad),
                        ('modo', parametros["modo"]),
                        ('periodo', parametros["periodo"]),
                        ('setpoint', parametros["setpoint"]),
                        ('rele estado', parametros["rele"])
                    ]))
                    await client.publish(f"sensores_remotos/{CLIENT_ID}", datos, qos = 1)
                except OSError as e:
                    print("sin sensor temperatura")
            except OSError as e:
                print("sin sensor humedad")
        except OSError as e:
            print("sin sensor")

        if parametros["modo"] == True:
            if temperatura>parametros["setpoint"]:
                parametros["rele"]=False
                pin_rele.value(0)
                escribir_db()
            else:
                parametros["rele"]=True
                pin_rele.value(1)
                escribir_db()
        

        await asyncio.sleep(parametros["periodo"]) 


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

def leer_db(parametro):
    with open("mydb", "r+b") as f:
        db = btree.open(f)
        resultado = db[parametro].decode()
        db.flush()
        db.close()
    return resultado

def escribir_db():
    with open("mydb", "w+b") as f:
        db = btree.open(f)
        print("Escribiendo")
        db[b"Periodo"] = b"{}".format(str(parametros["periodo"]))
            
        
        db[b"Setpoint"] = b"{}".format(str(parametros["setpoint"]))
            
        db[b"Modo"] = b"{}".format(str(parametros["modo"]))

        db[b"Rele"] = b"{}".format(str(parametros["rele"]))

        db.flush()
        db.close()



#async def task(client):
#    await asyncio.gather(transmitir(), main(client))

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