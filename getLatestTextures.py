import maya.cmds as cmds
import pymel.core as pm
import re
import os
from P4 import P4, P4Exception
import logging
logger = logging.getLogger(__name__)

def findTexturePaths():
	texSkip = []
	texData = []
	meshs = cmds.ls(typ='mesh')
	if not meshs:
		print ('no meshes')
	for mesh in meshs:
		shadeEng = cmds.listConnections(mesh, type='shadingEngine')
		if not shadeEng:
			continue
		materials = cmds.ls(cmds.listConnections(list(set(shadeEng))),materials=True)
		if not materials:
			continue

		for mat in materials:
			materialType = cmds.objectType(mat)

			if materialType == 'ShaderfxShader':
				texAttrs = cmds.listAttr(materials, uf=True)
				if not texAttrs:
					continue
				for attr in texAttrs:
					textureFile = cmds.getAttr('{}.{}'.format(mat, attr))
					try:
						textureFile = re.sub(r'//+', '/', textureFile)
					except:
						pass
					if not textureFile:
						continue
					if not textureFile in texSkip:
						texSkip.append(textureFile)
						cmds.warning('{} not found, skipping!'.format(textureFile))
					else:
						continue
					texData.append(textureFile)

			elif materialType == 'lambert' or materialType == 'blinn':
				fileNode = cmds.connectionInfo(('{}.color'.format(mat)),sfd=True).split('.')[0]
				if not fileNode:
					continue
				if not cmds.attributeQuery('fileTextureName', n=fileNode, exists=True):
					continue
				textureFile = cmds.getAttr('{}.fileTextureName'.format(fileNode))
				if not textureFile:
					continue
				if not textureFile in texSkip:
					texSkip.append(textureFile)
					cmds.warning('{} not found, skipping!'.format(textureFile))
				else:
					continue
				texData.append(textureFile)
	return texData

def ModifyTexturePaths(texturePaths):
	processedTextures = []
	perforcePaths = []
	for path in texturePaths:
		if path not in processedTextures:
			processedTextures.append(path)
			match = re.search(r'Potter', path, re.IGNORECASE)
			remainingPath = path[match.end():]
			perforcePath = '//' + 'Potter' + remainingPath.replace("\\", "/")
			# Ensure 'Textures' is capitalized properly
			segments = perforcePath.split('/')
			for i in range(len(segments)):
				if segments[i].lower() == 'textures':
					if i > 0 and segments[i - 1].lower() == '3d':
						segments[i] = 'Textures'
					else:
						segments[i] = 'textures'
			correctedPath = '/'.join(segments)
			perforcePaths.append(correctedPath)
	return perforcePaths

def connectToPerforce():
	p4 = P4()
	try:
		p4.connect()
		return p4
	except P4Exception as e:
		logger.error("Failed to connect to Perforce: %s", e)
		return None
	
def checkAndUpdateTexture(p4, perforcePaths):
	getLatestPaths = []
	errorMessages = []
	noChanges = []

	for path in perforcePaths:
		try:
			# Check if the file exists locally
			localFileInfo = p4.run('fstat', path)
			localFileExists = os.path.exists(localFileInfo[0]['clientFile']) if localFileInfo else False

			if not localFileExists:
				p4.run_sync('-f', path)
				getLatestPaths.append(f"Downloaded missing file: {path}")
				continue

			# Fetch the latest file revision
			fileInfo = p4.run('files', path)
			if not fileInfo:
				errorMessages.append(f"File not found in Perforce: {path}")
				continue

			depotRev = fileInfo[0].get('rev')
			localRev = localFileInfo[0].get('haveRev')
			print(f"Checking path: {path}")
			print(f"Local revision: {localRev}, Latest depot revision: {depotRev}")

			if depotRev and localRev and depotRev != localRev:
				p4.run_sync(path)
				getLatestPaths.append(f"Updated {path} to revision {depotRev}")
			elif depotRev and localRev and depotRev == localRev:
				noChanges.append(f"Already at the latest version: {path}")
			else:
				errorMessages.append(f"Revision data missing for path: {path}")

		except P4Exception as e:
			errorMessages.append(f"Error handling texture: {path} {e}")

	return getLatestPaths, errorMessages, noChanges

'''Begin loop'''
def getLatestTex():
	
	# Get all file paths for materials used in the scene
	print ('\nFinding texture paths...')
	localPaths = findTexturePaths()
	print (localPaths)

	# Modify texture paths
	print ('\nModifying texture paths...')
	perforcePaths = ModifyTexturePaths(localPaths)
	print (perforcePaths)
	
	# Connect to Perforce:
	p4 = connectToPerforce()
	if not p4:
		print("Failed to connect to Perforce.")
		return
	
	# Update textures
	getLatestPaths, errorMessages, noChanges = checkAndUpdateTexture(p4, perforcePaths)
	p4.disconnect()
	
	# Print results
	print('\n'+'=' * 30 + '\n       Untouched Files:\n' + '=' * 30 +'\n')
	for message in noChanges:
		print(message)
	print('\n'+'=' * 30 + '\n       Failed to get latest:\n' + '=' * 30 +'\n')
	for message in errorMessages:
		print(message)
	print('\n'+'=' * 30 + '\n       Got latest files:\n' + '=' * 30)
	for message in getLatestPaths:
		print(message)

	print('\n=== COMPLETE! See above for details ===')
