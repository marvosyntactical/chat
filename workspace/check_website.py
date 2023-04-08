import requests
import time

url = 'https://www.cl.uni-heidelberg.de/'
wait_time = 600

while True:
    response = requests.get(url)
    if response.status_code == 200:
        print('Website is up!')
    else:
        print('Website is down!')
    time.sleep(wait_time)
