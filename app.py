import requests,json,schedule,time,os,threading,qrcode,random,string
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_session import Session
from collections import defaultdict
####################################################
base_url = "https://api.meraki.com/api/v1"
payload = None

app = Flask(__name__)
app.config['SESSION_TYPE'] = 'redis'
Session(app)
# Set the absolute path to save the data.json file in the current directory
DATA_FILE_PATH = os.path.join(os.getcwd(), 'data.json')
current_frequency = int(1)
current_unit = "minutes"
####################################################
### Meraki API calls
## Getting the list of Orgs the API key has access to
def getOrgs():
    url = base_url + "/organizations"
    headers = {
    "Accept": "application/json",
    "Authorization": f"Bearer {session['api']}"
    }

    response = requests.request('GET', url, headers=headers, data = payload)
    result = json.loads(response.text)
    return result
## Getting the networks mapped to org
def getNetworks(organizationId):
    url = base_url + f"/organizations/{organizationId}/networks"
    headers = {
    "Accept": "application/json",
    "Authorization": f"Bearer {session['api']}"
    }
    response = requests.request('GET', url, headers=headers, data = payload)
    result = json.loads(response.text)
    return result
## Get the list of SSIDs mapped to a network
def getSSID(networkId):
    url = base_url + f"/networks/{networkId}/wireless/ssids"
    headers = {
    "Accept": "application/json",
    "Authorization": f"Bearer {session['api']}"
    }
    response = requests.request('GET', url, headers=headers, data = payload)
    if response.status_code == 200:
        result = json.loads(response.text)
    else:
        print(f"issue with query {response}")
        result = "Issue with SSID query"

    return result,response.status_code
## Change the password of the SSID
def changeSSIDPassword(api,networkId,number,newPassword):
    url = base_url + f"/networks/{networkId}/wireless/ssids/{number}"
    payload ={'authMode':'psk',
              "encryptionMode": "wpa",
              "wpaEncryptionMode": "WPA2 only",
              'psk': newPassword}
    headers = {
    "Accept": "application/json",
    "Authorization": f"Bearer {api}"
    }
    response = requests.request('PUT', url, headers=headers, data = payload)
    result = json.loads(response.text)
    return result
####################################################
### Section to generate passwords and save data
## Auto Generate Password
def generate_password(length=26):
    if length < 16:  # we need space for each type of character
        print("Password length should be at least 4")
        return None

    # Define characters set. For the sake of easier typing, limit the special characters.
    special_chars = "!@#$%^&*()-_=+"
    password = []
    # Ensure at least one character from each character set is included
    password.append(random.choice(string.ascii_lowercase))
    password.append(random.choice(string.ascii_uppercase))
    password.append(random.choice(string.digits))
    password.append(random.choice(special_chars))

    # Fill the remaining length with a mix of all character sets
    for i in range(length - 4):
        password.append(random.choice(string.ascii_letters + string.digits + special_chars))

    # Shuffle the characters randomly to ensure randomness even with the initial mandatory characters
    random.shuffle(password)
    return ''.join(password)
## Save the collected data locally on JSON file
def saveDataLocal(user_data):
    with open(DATA_FILE_PATH, 'w') as f:
        json.dump(user_data, f)
    return 'Data saved successfully!'
## Generate a QR code of the SSID and password configured and save and return the image path 
def generate_wifi_qr(ssid, password):
    wifi_info = f"WIFI:T:WPA;S:{ssid};P:{password};;"
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=4,
    )
    qr.add_data(wifi_info)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white")
    qr_img.save(f"./static/{ssid}.png")
    imagePath = f"./static/{ssid}.png"
    return imagePath
## Construct the dictionary of data to be saved
def DataToSave(preshared,api,ssids,selected_networks,selected_ssids,change_frequency,change_unit):
    data ={
        "_id": None,
        "change_frequency":int(change_frequency),
        "change_unit":change_unit,
        "preshared": preshared,
        "api": api,
        "SSIDs": ssids,
        "selected_networks": selected_networks,
        "selected_ssids":selected_ssids
    }
    return data
## Remove the JSON file local
def delete_file(file_path=DATA_FILE_PATH):
    try:
        os.remove(file_path)
        print(f"The file {file_path} has been deleted.")
        return "The schedule has been stopped."
    except FileNotFoundError:
        print(f"No such file: {file_path}")
        return "No schedules are running"
    except PermissionError:
        print(f"Permission denied: {file_path}")
        return "Permission denied"
    except Exception as e:
        print(f"Unable to delete the file due to: {str(e)}")
        return f"Error due to: {str(e)}"
# Function to read and change password from the json file
def ReadSavedStartPasswordChange():
    images = []
    if os.path.exists(DATA_FILE_PATH):
        with open(DATA_FILE_PATH, 'r') as f:
            data = json.load(f)

        ## Going over the selected SSIDs by the user that is saved in data.json file
        for selected_SSID in data['selected_ssids']:
            for SSID in data["SSIDs"]:
                ## match on the SSID name and the network selected by the user
                if (SSID['name'] == selected_SSID) and (SSID['networkName'] in data['selected_networks']):
                        data['preshared'] = generate_password()
                        ## Run the password change
                        newSSIDpassword = changeSSIDPassword(data['api'],SSID['id'],SSID['number'],data['preshared'])
                        ## save the list of image generated QR code locally
                        images.append(generate_wifi_qr(SSID['name'],data['preshared']))
    return images
####################################################
def run_schedule():
    global current_frequency, current_unit
    # Initialize the schedule with default values
    schedule.every(current_frequency).minutes.do(ReadSavedStartPasswordChange)
    while True:
        if os.path.exists(DATA_FILE_PATH):
            with open(DATA_FILE_PATH, 'r') as f:
                data = json.load(f)
                if 'change_frequency' in data and 'change_unit' in data and (data['change_frequency'] != current_frequency or data['change_unit'] != current_unit):
                    schedule.clear()
                    current_frequency = data['change_frequency']
                    current_unit = data['change_unit']
                    
                    if current_unit == 'minutes':
                        schedule.every(current_frequency).minutes.do(ReadSavedStartPasswordChange)
                    elif current_unit == 'hours':
                        schedule.every(current_frequency).hours.do(ReadSavedStartPasswordChange)
                    elif current_unit == 'days':
                        schedule.every(current_frequency).days.do(ReadSavedStartPasswordChange)
                    elif current_unit == 'weeks':
                        schedule.every(current_frequency).weeks.do(ReadSavedStartPasswordChange)

        schedule.run_pending()
        time.sleep(1)
## The app CaptureDetails to verify the API key first then starting to get the Orgs / Networks / SSID details and return them
def CaptureDetails():
    network_SSID =[]
    network_list =[]
    fullSSIDs = []
    ## Capturing all the orgs of the API key
    orgs = getOrgs()
    if 'errors' not in orgs:
        ## if there is no error in the result of orgs, going through a loop to capture all the networks
        for org in orgs:
            print(org['name'])
            networks = getNetworks(org['id'])
            ## Going through the networks and look for only networks that has wireless and save the result in a list of networks
            for network in networks:
                if'wireless' in network['productTypes']:
                    network_list.append(network['name'])
                    ## Capturing the SSIDs of each network and making sure the outcome is successful
                    SSIDs,SSID_status = getSSID(network['id'])
                    if SSID_status != 200:
                        continue
                    else:
                        ## saving the SSID after adding info of org, network details
                        for SSID in SSIDs:
                            SSID['id'] = network['id']
                            SSID['networkName'] = network['name']
                            SSID['orgID'] = org['id']
                            SSID['orgName'] = org['name']
                            fullSSIDs.append(SSID)
                            if SSID['name'] not in network_SSID:
                                network_SSID.append(SSID['name'])

    else:
        ## If the API is wrong, it will return wrongAPI to allow the user to re-enter the correct API key again
        print(f"There is error {orgs['errors']}")
        return "wrongAPI","",""

    return network_list,network_SSID,fullSSIDs
####################################################

@app.route('/', methods=['GET', 'POST'])
def index():
    ## When the user hit Submit the API key we will save it in the session and redirect to networks path
    if request.method == 'POST':  
        # Store or process the API key as needed
        session["api"] = request.form.get('api_key')
        return redirect(url_for('networks'))
    ## if the method is GET, the user will be welcomed with index HTML to enter the API key
    return render_template('index.html')

@app.route('/networks', methods=['GET', 'POST'])
def networks():
    if request.method == 'GET':
         ## After the user submit the API key, we will CaptureDetails the script and capture the networks and SSIDs the API key has access to
        session["network_list"],session["network_SSID"],session['SSIDs'] = CaptureDetails()
        ## we will organize the result to present them grouped with Org Names in the HTML and save them on grouped_items
        grouped_items = defaultdict(list)
        for item in session['SSIDs']:
            grouped_items[item['orgName']].append(item)

        ## If the API key is wrong, we will reload the index HTML with banner to re-enter the correct API key
        if session["network_list"] == "wrongAPI":
            flash("You have supplied invalid API key!", "danger")
            return redirect(url_for('index'))
        
    if request.method == 'POST':
        ## After the user select the Networks and SSIDs as well as the pre-shared key that needed the script to change to, we will save the data in the session and redirect to result
        session['preshared'] = generate_password()
        session['selected_items_list1'] = request.form.getlist('choice1')
        session['selected_items_list2'] = request.form.getlist('choice2')
        session['change_frequency'] = request.form.get('change_frequency')
        session['change_unit'] = request.form.get('change_unit')
        return redirect(url_for('results'))
    
    return render_template('networks.html', list1=session['network_list'], list2=session['network_SSID'],networkSSID=grouped_items)

@app.route('/results', methods=['GET'])
def results():
    ## After user selected the networks and SSIDs, the data will be organized and saved locally
    session['resultData'] = DataToSave(session.get('preshared'),session.get('api'),session.get('SSIDs'),session.get('selected_items_list1', []),session.get('selected_items_list2', []),session.get("change_frequency"),session.get("change_unit"))
    saveDataLocal(session['resultData'])

    return render_template('results.html', selected_items_list1=session.get('selected_items_list1', []), selected_items_list2=session.get('selected_items_list2', []))

@app.route('/stop', methods=['GET'])
def stop():
    ## Delete the JSON file
    alertmessage = delete_file()
    flash(alertmessage, "success")
    return redirect(url_for('index'))

if __name__ == '__main__':
    t = threading.Thread(target=run_schedule)
    t.start()
    app.run(host="0.0.0.0",port=5000)

