# trelloJsonSummary.py - create a text summary of trello cards from exported json

import json
import logging
import chardet

logging.basicConfig(
        level=logging.INFO,
        # format='%(asctime)s %(message)s',
        format='%(message)s',
        handlers=[
            logging.FileHandler('trelloJsonSummary.log','w'),
            logging.StreamHandler()
        ]
)

trelloJsonFilename='trello_20220701.json'
enc='utf-8'
logging.info('reading '+trelloJsonFilename+'...')
with open(trelloJsonFilename,'rb') as tjfe:
    enc=chardet.detect(tjfe.read())['encoding']
    # logging.info('encoding:'+str(enc))

tj=None
with open(trelloJsonFilename,'r',encoding=enc) as trelloJsonFile:
    tj=json.load(trelloJsonFile)
if not tj:
    exit()

lists=tj['lists']
openLists=[l for l in lists if not l['closed']]
logging.info(str(len(openLists))+' open lists extracted:'+str([l['name'] for l in openLists]))
# add a 'cards' key to each list, initial value = empty list, and fill it while iterating through all cards
for list in lists:
    list['cards']=[]

cards=tj['cards']
# logging.info('Extracted json:\n'+json.dumps(tj,indent=3))
logging.info(str(len(cards))+' cards extracted')
for card in cards:
    # logging.info('\nNEXT CARD:\n-----------\n'+json.dumps(card,indent=3))
    list=[l for l in lists if l['id']==card['idList']][0] # this assumes there is exactly one matching list
    if list:
        list['cards'].append(card)
    else:    
        logging.error('listId for card "'+card['name']+'" did not match any discovered list.  Please check the json file directly.')

# show the summary
for list in lists:
    if list['closed']:
        continue
    listCards=list['cards']
    logging.info('\nLIST: '+list['name']+'  -->  '+str(len(listCards))+' card(s)')
    for card in listCards:
        logging.info('   '+card['name'])
    

