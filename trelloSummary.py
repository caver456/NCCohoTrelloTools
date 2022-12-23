# trelloSummary.py - generate a summary report from the NCCoHo Maintenance Networkers Trello board

import requests
import json
import time
import os
import sys
from datetime import datetime
from collections import defaultdict

API_KEY=os.getenv('TRELLO_API_KEY','')
API_TOKEN=os.getenv('TRELLO_API_TOKEN', '')
BOARD_ID=os.getenv('TRELLO_BOARD_ID','') # not really a secret, but seems better to not hardcode it

apiUrlBase='https://api.trello.com/1/'

outString=''

def rprint(text):
	print(text)
	global outString
	outString+=text+'\n'

if not API_KEY or not API_TOKEN:
	rprint('ERROR: TRELLO_API_KEY and/or TRELLO_API_TOKEN are not defined as environment variables.  Aborting.')
	sys.exit(-1)

now=datetime.now()
timeStr=now.strftime('%A %B %#d %Y, %#I:%M %p')
rprint('NCCoHo Maintenance Report - generated '+timeStr)

def get(type,id=None,recursion=0):
	params={'key':API_KEY,'token':API_TOKEN}
	if type not in ['board','lists','cards','customFieldItems']:
		rprint('Invalid type requested: "'+str(type)+'"')
		return None
	if type=='board':
		type='boards/'+BOARD_ID
		params['customFields']='true'
		params['cards']='all'
		params['fields']='all'
		params['members']='all'
		params['labels']='all'
		params['lists']='all'
	if type=='lists':
		type='boards/'+BOARD_ID+'/lists'
	if type=='cards':
		type='boards/'+BOARD_ID+'/cards'
		params['customFieldItems']='true' # doesn't work in boards request
	if type=='customFieldItems':
		type='cards/'+id+'/customFieldItems'
	fullUrl=apiUrlBase+type
	# print('fullUrl: '+fullUrl)
	r=requests.get(fullUrl,params=params)
	# print('status: '+str(r.status_code))
	if r.status_code==200:
		with open(type.replace('/','_')+'.json','w') as f:
			f.write(json.dumps(r.json(),indent=3))
		# print(json.dumps(r.json(),indent=3))
		return r.json()
	elif r.status_code==429: # rate-limited: 100 requests per 10 second interval per token
		if recursion<10:
			rprint(' API rate limit exceeded - waiting a few seonds then retrying...')
			time.sleep(2)
			get(type,id,recursion+1)
		else:
			rprint(' API rate limit exceeded more than 10 times in a row; giving up on this request.')
			return None
	else:
		return r.text

listIdDict={}
board=get('board',BOARD_ID)
# _lists=get('lists')
# cards=get('cards')
_lists=[l for l in board['lists'] if not l['closed']] # exclude closed(archived) lists right off the bat
# cards=[c for c in board['cards'] if not c['closed']] # exclude closed(archived) cards right off the bat
cards=[c for c in get('cards') if not c['closed']] # exclude closed(archived) cards right off the bat

# to make the sorting and filtering code easier,
#  modify the board json by adding a priority key to each card,
#  with corresponding value from that card's customFields
# it might be 'cleaner' to leave the json exactly as it is returned by the API,
#  but this seems like a reasonable deviation

boardCustomFields=board['customFields']
boardPriorityFieldList=[f for f in boardCustomFields if f['name']=='Priority']
if boardPriorityFieldList: # the list will be empty if no priority field is defined
	boardPriorityField=boardPriorityFieldList[0]
	# print(json.dumps(boardPriorityField,indent=3))
	for card in cards:
		# cardCustomFields=get('customFieldItems',card['id'])
		cardCustomFields=card['customFieldItems'] # will be an empty list if no custom field values are set for this card
		cardPriorityFieldList=[f for f in cardCustomFields if f['idCustomField']==boardPriorityField['id']]
		if cardPriorityFieldList: # the list will be empty if priority has not been set
			cardPriorityField=cardPriorityFieldList[0]
			# print(json.dumps(cardPriorityField,indent=3))
			cardPriorityValueId=cardPriorityField['idValue']
			optionList=[option for option in boardPriorityField['options'] if option['id']==cardPriorityValueId]
			if optionList: # the list will be empty if no matching option exists
				option=optionList[0]
				card['priority']=option['value']['text']
		else:
			card['priority']='Other'

# build a dict of members: key = member id; val - full member json
memberDict=defaultdict(dict)
for member in board['members']:
	memberDict[member['id']]=member

ownerCardDict=defaultdict(dict)

# now do the main iteration and report generation
for _list in _lists:
	idList=_list['id']
	listName=_list['name']
	priorityDict=defaultdict(list)
	for card in cards:
		if card['idList']==idList:
			priorityDict[card['priority']].append(card)
			# print('   CARD: '+card['priority'][0]+' : '+card['name'])
	rprint('\n'+listName+' : '+str(sum(len(p) for p in priorityDict.values()))+' cards')
	for memberId in memberDict.keys():
		ownerCardDict[memberDict[memberId]['initials']][listName]=defaultdict(list)
	for priority in ['High','Medium','Low','Other']:
		# for memberId in memberDict.keys():
		# 	ownerCardDict[memberId][idList][priority]=[]
		count=len(priorityDict[priority])
		if count>0: # don't print the priority line if there are no cards with that priority level
			prefix=priority+' priority:'
			if priority=='Other':
				prefix='Other:'
			rprint('  '+prefix+' '+str(count)+' cards')
			for card in priorityDict[priority]:
				# card creation timestamp is the first 8 hex characters of the ID
				# https://support.atlassian.com/trello/docs/getting-the-time-a-card-or-board-was-created/
				ts=int(card['id'][0:8],base=16)
				ownerText=''
				if card['idMembers']:
					ownerText=' - '
					for memberId in card['idMembers']:
						if len(ownerText)>4:
							ownerText+=', '
						ownerText+=memberDict[memberId]['initials']
				cardText=('    '+card['name']+' ('+datetime.fromtimestamp(ts).strftime('%x')+ownerText+')')
				rprint(cardText)
				for memberId in card['idMembers']:
					ownerCardDict[memberDict[memberId]['initials']][listName][priority].append(cardText)

# write the overall summary file
with open('out.txt','w') as outFile:
	outFile.write(outString)

# print(json.dumps(ownerCardDict,indent=3))

# write the individual summary files
for initials in ownerCardDict.keys():
	outString='NCCoHo Maintenance Report for '+initials+' - generated '+timeStr+'\n'
	for (listName,priorityDict) in ownerCardDict[initials].items():
		if listName not in ['Monitor','Complete']:
			if len(priorityDict.items())>0:
				outString+='\n'+listName+':\n'
				for (priority,prioritizedCards) in priorityDict.items():
					prefix=priority+' priority:'
					if priority=='Other':
						prefix='Other:'
					for card in prioritizedCards:
						outString+=card+'\n'
	if not outString:
		outString='Nothing to report for member '+initials
	with open(initials+'_summary.txt','w') as outFile:
		outFile.write(outString)

# determining a card's priority:
# - get the card's customFields json ['CCF']
# - get the board's customFields json (can be done as a parameter in the 'boards' request) ['BCF']
# - BCF only defines the custom fileds and their options
# - BCF will have one entry per defined custom field
# - CCF will have one entry per board-defined custom field, regardless of whether a value has been set
# - CCF[m]['idCustomField'] will be of BCF[n]['id']
# - CCF[m]['idValue'] will be one of BCF[n]['options'][j][id']

# example:
# cards/639b3d7fd06a4501e4786d40/customFields:
# [
#    {
#       "id": "639b3e385d834801be2babb1",
#       "idValue": "5fecb023cbfde82268ed7689",
#       "idCustomField": "5fecb023cbfde82268ed7686",
#       "idModel": "639b3d7fd06a4501e4786d40",
#       "modelType": "card"
#    },
#    {
#       "id": "639b3e3ea296c00030a791c7",
#       "value": {
#          "date": "2022-12-04T20:00:00.000Z"
#       },
#       "idCustomField": "5fecb034edcf5980122dd625",
#       "idModel": "639b3d7fd06a4501e4786d40",
#       "modelType": "card"
#    },
#    {
#       "id": "639b3e40601aae0289d92899",
#       "value": {
#          "text": "Tom"
#       },
#       "idCustomField": "5fecb041b9fcee2e79cde9f8",
#       "idModel": "639b3d7fd06a4501e4786d40",
#       "modelType": "card"
#    }
# ]

# boards/5fecaa2517be8365eb37fe77:
# ...
#    "customFields": [
#       {
#          "id": "5fecb023cbfde82268ed7686",
#          "idModel": "5fecaa2517be8365eb37fe77",
#          "modelType": "board",
#          "fieldGroup": "b0cddfb41bc9462347387c37077a2de5338a50c797e04f3cf0adb6ae2344e83c",
#          "display": {
#             "cardFront": true
#          },
#          "name": "Priority",
#          "pos": 16384,
#          "options": [
#             {
#                "id": "5fecb023cbfde82268ed7687",
#                "idCustomField": "5fecb023cbfde82268ed7686",
#                "value": {
#                   "text": "Low"
#                },
#                "color": "green",
#                "pos": 19456
#             },
#             {
#                "id": "5fecb023cbfde82268ed7688",
#                "idCustomField": "5fecb023cbfde82268ed7686",
#                "value": {
#                   "text": "Medium"
#                },
#                "color": "yellow",
#                "pos": 35840
#             },
#             {
#                "id": "5fecb023cbfde82268ed7689",
#                "idCustomField": "5fecb023cbfde82268ed7686",
#                "value": {
#                   "text": "High"
#                },
#                "color": "red",
#                "pos": 52224
#             }
#          ],
#          "type": "list",
#          "isSuggestedField": false
#       },
#       {
#          "id": "5fecb034edcf5980122dd625",
#          "idModel": "5fecaa2517be8365eb37fe77",
#          "modelType": "board",
#          "fieldGroup": "779c58c00699a23c0e30fdf4b6d2492003198c94bd6ef303795e53593f503df5",
#          "display": {
#             "cardFront": true
#          },
#          "name": "Reported",
#          "pos": 32768,
#          "type": "date",
#          "isSuggestedField": false
#       },
#       {
#          "id": "5fecb041b9fcee2e79cde9f8",
#          "idModel": "5fecaa2517be8365eb37fe77",
#          "modelType": "board",
#          "fieldGroup": "905f7f27ee6a9bd0690eeefdbfb35280d1584f4f9d9b73d64fa69b09b6a27760",
#          "display": {
#             "cardFront": false
#          },
#          "name": "Reported By",
#          "pos": 49152,
#          "type": "text",
#          "isSuggestedField": false
#       }
#    ],
# ...


# from https://github.com/jtpio/trello-full-backup/blob/master/trello_full_backup/backup.py
# board_details = requests.get(''.join((
# 	'{}boards/{}{}&'.format(API, board["id"], auth),
# 	'actions=all&actions_limit=1000&',
# 	'cards={}&'.format(FILTERS[args.archived_cards]),
# 	'card_attachments=true&',
# 	'labels=all&',
# 	'lists={}&'.format(FILTERS[args.archived_lists]),
# 	'members=all&',
# 	'member_fields=all&',
# 	'checklists=all&',
# 	'fields=all'
# ))).json()
# for card in cards:
# 	print('CARD:'+card['name'])


