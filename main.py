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
import dht, machine
from collections import OrderedDict
import ujson as json
import ubinascii
import btree
import time
from machine import Timer
import settings

CLIENT_ID = ubinascii.hexlify(machine.unique_id()).decode('utf-8')
d = dht.DHT22(machine.Pin(13))
pin_rele = dht.DHT22(machine.Pin(36))
pin_led = dht.DHT22(machine.Pin(2))


setpoint=40
#modo automatico = TRUE, MANUAL = FALSE
modo=True
#periodo en ms
periodo=30000
#rele empieza apagado
rele_estado=False
datos={}

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
    print(f"publicando en {CLIENT_ID}")
    client.connect()
    client.publish(f"CLIENT_ID",datos, qos = 1)
    client.disconnect()

def sub_cb(topic, msg, retained):
    print('Topic = {} -> Valor = {}'.format(topic.decode(), msg.decode()))

async def wifi_han(state):
    print('Wifi is ', 'up' if state else 'down')
    await asyncio.sleep(1)

# If you connect with clean_session True, must re-subscribe (MQTT spec 3.1.2.4)
async def conn_han(client):
    await client.subscribe(f"CLIENT_ID", 1)

async def main(client):
    await client.connect()

    for coroutine in (up, messages):
        asyncio.create_task(coroutine(client))

    await asyncio.sleep(2)  # Give broker time

    await client.publish(f"CLIENT_ID","inciiando", qos = 1)
    
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
            await client.publish(CLIENT_ID,"hola")
        except OSError as e:
            print("sin sensor temperatura")
        if modo == True:
            if temperatura>setpoint:
                rele_estado=True
            else:
                rele_estado=False

        pin_rele.value(rele_estado)

        db[b"Temperatura"] = str(temperatura)
        db[b"Humedad"] = str(humedad)
        db[b"Rele Estado"] = str(rele_estado)
        db.flush()
        await asyncio.sleep(180)  # Broker is slow

timer_publicar=Timer(0)
timer_publicar.init(period=periodo, mode=Timer.PERIODIC, callback=transmitir)



async def up(client):  # Respond to connectivity being (re)established
    while True:
        await client.up.wait()  # Wait on an Event
        client.up.clear()
        await client.subscribe(f'{CLIENT_ID}/temperatura', 1)  # renew subscriptions
        await client.subscribe(f'{CLIENT_ID}/humedad', 1)  # renew subscriptions
        await client.subscribe(f'{CLIENT_ID}/rele', 1)  # renew subscriptions
        await client.subscribe(f'{CLIENT_ID}/modo', 1)  # renew subscriptions
        await client.subscribe(f'{CLIENT_ID}/periodo', 1)  # renew subscriptions
        await client.subscribe(f'{CLIENT_ID}/destello', 1)  # renew subscriptions

async def messages():
    async for topic, msg, retained in client.queue:
        if topic == f"{CLIENT_ID}/periodo":
            periodo = int(msg)
            timer_publicar=Timer(0)
            timer_publicar.init(period=periodo, mode=Timer.PERIODIC, callback=transmitir)
        
        if topic == f"{CLIENT_ID}/setpoint":
            setpoint = int(msg)

        if topic == f"{CLIENT_ID}/modo":
            if msg == "auto":
                modo = True
            elif msg == "manual":
                modo = False
            print(f"modo = {msg}")

        if topic == f"{CLIENT_ID}/rele":
            if msg == "on":
                rele_estado = True
            elif msg == "off":
                rele_estado = False

        if topic == f"{CLIENT_ID}/destello":
            if msg == "on":
                destello()

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

