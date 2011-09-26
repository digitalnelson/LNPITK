#    This program is part of the University of Minnesota Labratory for
#    NeuroPsychiatric Imaging ToolKit
#
#    LNPITK is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
#    Copyright 2011 Brent Nelson

import datetime as dt
import collections as cs
import numpy as np
import scipy.stats as ss
import networkx as nx
import cPickle as pk

#This is a python implementation of the Network-base statistic proposed by Andrew Zalesky in his 
#paper Network-based statistic: Identifying differences in brain networks.
#Zalesky A, Fornito A, Bullmore ET. Network-based statistic: Identifying differences in brain networks. 
#NeuroImage. 2010. Available at: http://linkinghub.elsevier.com/retrieve/pii/S1053811910008852 [Accessed July 1, 2010].

class DataParameters():
	
	def __init__(self, label, threshold, totalNodes):
		self.label = label
		self.threshold = threshold
		self.totalNodes = totalNodes

class TStatResult():
	
	def __init__(self):
		
		self.tStats = None
		self.pVals = None

class Component():

	def __init__(self, rawSubGraph):

		self.rawSubGraph = rawSubGraph
		self.pVal = None
		
	def nodes(self):
		return self.rawSubGraph.nodes()
	
	def edges(self):
		return self.rawSubGraph.edges()
		
	def size(self):
		return self.rawSubGraph.size()
	
	def len(self):
		return len(self.rawSubGraph)
		
class Graph():
	
	def __init__(self):
		
		self.rawGraph = nx.Graph()
		self.components = []
		self.largestComponent = None
		
	def setCoords(self, coords):
		
		# Build base graph
		for coord in coords:
			self.rawGraph.add_edge(*coord)

		# Get all of the subgraphs of this graph
		rawSubGraphs = nx.components.connected_component_subgraphs(self.rawGraph)
		
		# Pull out the largest component of this graph
		for rawSubGraph in rawSubGraphs:

			component = Component(rawSubGraph)
			self.components.append(component)
			
			if (self.largestComponent == None) or (rawSubGraph.size() > self.largestComponent.size()):
				self.largestComponent = component
		return
	
	def getComponentCount(self):

		return len(self.components)

	def getLargestComponentSize(self):
	
		if self.largestComponent != None:
			return self.largestComponent.size()
		else:
			return 0

	@staticmethod
	def getNodeOverlapStrict(graphs):
	
		base = []
		overlap = []
		
		for graph in graphs:
	
			if graph.largestComponent == None:
				return []
			
			if len(base) == 0:
				for node in graph.largestComponent.nodes():
					base.append(node)
			else:
				for node in graph.largestComponent.nodes():
					if node in base:
						overlap.append(node)
		return overlap
		
class GroupResult():
	
	def __init__(self):
		self.dataSeriesGraphs = {}
		
	def addGraph(self, dataParameter, graph):
		self.dataSeriesGraphs[dataParameter.label] = graph
		
	def getNodeOverlap(self):
		return Graph.getNodeOverlapStrict(self.dataSeriesGraphs.values())

class PermutationResult():
	
	def __init__(self):
		# Member to hold raw group results
		self.groupResults = []
		self.groupResultsLength = 0
		
		self.cmpExtBySeries = cs.defaultdict(list)
		self.nodeOverlapCounts = []
		self.nodeTotals = {}
		
	def addResult(self, grpRes):
		
		# Save the individual permutation result
		# TODO: Might have to eliminate this eventually d/t size/memory issues
		#self.groupResults.append(grpRes)
		self.groupResultsLength = self.groupResultsLength + 1

		# Store the largest component extent for each data series
		for label, graph in grpRes.dataSeriesGraphs.iteritems():
			self.cmpExtBySeries[label].append(graph.getLargestComponentSize())
		
		# Get list of overlapping nodes
		nodes = grpRes.getNodeOverlap()
		
		# Save count of overlapping nodes
		self.nodeOverlapCounts.append(len(nodes))
		
		# Keep track of overlapping node ids as well as total permutation counts
		for node in nodes:
			if self.nodeTotals.has_key(node):
				self.nodeTotals[node] = self.nodeTotals[node] + 1
			else:
				self.nodeTotals[node] = 1

	def getComponentPVal(self, seriesLabel, componentExtent):

		seriesDist = self.cmpExtBySeries[seriesLabel]
		seriesDist = np.array(seriesDist)
		
		# Find the number of components (from the distribution) larger than this one
		idxs = np.where(seriesDist > componentExtent)
	
		if len(idxs[0]) > 0:
			# Calculate the pvalue
			return float(float(len(idxs[0])) / float(self.groupResultsLength))
		else:
			return 0

	def getOverlapNodePVal(self, ident):
		if self.nodeTotals.has_key(ident):
			nodeCount = self.nodeTotals[ident]
			return nodeCount, self.groupResultsLength, float(int(nodeCount)) / float(self.groupResultsLength)
		else:
			return 0, len(self.groupResults), 0

	def getMaxOverlapSize(self):
		return np.max(self.nodeOverlapCounts)
	
	def getOverlapHistogram(self):
		return np.bincount(self.nodeOverlapCounts)

class ComparisonResult():
	
	def __init__(self):
		self.actualResult = None
		self.permutationResult = None

class DataCacheItem():
	
	def __init__(self):
		self.subjectIndex = None
		self.data = None
		
class tStatNBS():
	
	def __init__(self):
		self.subDataByLabel = {}
	
	def cacheData(self, group1, group2, dataParameters):

		#if np.size(group1, axis=1) != np.size(group2, axis=1):
		#	raise IndexError()
		
		subs = []
		subs.extend(group1)
		subs.extend(group2)
		
		for parm in dataParameters:

			dci = DataCacheItem()
			
			dci.subjectIndex = {}
			dci.data = None
			
			self.subDataByLabel[parm.label] = dci
			
			for idx, sub in enumerate(subs):

				data = np.asarray(sub.data[parm.label]).flatten()
				
				if dci.data == None:
					dci.data = np.empty( (len(subs), data.shape[0]) )
				
				dci.subjectIndex[sub.subjectId] = idx
				dci.data[idx] = data
		return
				
	def getSubjectData(self, subject, dataParameter):
	
		subDataKey = str(subject.subjectId) + dataParameter.label
		
		if self.cachedSubjectData.has_key(subDataKey):
			return self.cachedSubjectData[subDataKey]
		else:
			dataItm = np.asarray(subject.data[dataParameter.label]).flatten()
			self.cachedSubjectData[subDataKey] = dataItm
			return dataItm
			
		
	def tTestGroups(self, group1, group2, dataParameter):
		'''This method takes two groups of subjects and compares their data by label and returns tStats and 
		pVals for that label.  It flattens the data before comparing.'''

		dataCache = self.subDataByLabel[dataParameter.label]
		
		# Pull and flatten the data for each of the groups and store
		# in a temporary array
		grp1 = []
		for subject in group1:
			dataIdx = dataCache.subjectIndex[subject.subjectId]
			grp1.append(dataIdx)
			
		grp2 = []
		for subject in group2:
			dataIdx = dataCache.subjectIndex[subject.subjectId]
			grp2.append(dataIdx)

		grp1Data = dataCache.data[grp1]
		grp2Data = dataCache.data[grp2]
	
		result = TStatResult()
		
		# Generate T stats and P vals for each array index by comparing groups using independent T test
		resArr = ss.ttest_ind(grp1Data, grp2Data, axis = 0)
		result.tStats = resArr[0]
		result.pVals = resArr[1]
		
		return result
		
	def compareGroups(self, group1, group2, dataParameters):
		'''Creates a graph for each data label that is made up of nodes that are above the thresh 
		tstat of interest.  Note:  group1 and group2 must be the same axis 1 length'''
		
		result = GroupResult()
	
		for dataParameter in dataParameters:
	
			# Pull out the comparison result for this label
			tresult = self.tTestGroups(group1, group2, dataParameter)
			
			# Change tStats into mtx of shape nodeCount X nodeCount
			tStatMtx = np.abs(tresult.tStats.reshape((dataParameter.totalNodes, dataParameter.totalNodes)))
			
			# Figure out which i,j are above our threshold and mark them with a 1
			supraThreshLinks = np.where(tStatMtx > dataParameter.threshold)
			supraThreshAdjMtx = np.zeros((dataParameter.totalNodes, dataParameter.totalNodes))
			supraThreshAdjMtx[supraThreshLinks] = 1
	
			# Create an NBSGraph to contain our suprathresh results
			graph = Graph()
			
			# Store our suprathresh coords
			graph.setCoords(zip(*np.where(supraThreshAdjMtx > 0)))
		
			# Store the graph for this data series
			result.addGraph(dataParameter, graph)
		
		return result
	
	def getRandomDistribution(self, group1, group2, dataParameters, iterations):
	
		allSubjects = []
	
		# Put all subjects together for easy shuffling
		allSubjects.extend(group1)
		allSubjects.extend(group2)
		
		result = PermutationResult()
				
		# Perform desired # of iterations
		for i in range(iterations):
	
			# Mix up all of the subjects
			np.random.shuffle(allSubjects)
	
			# Grab new groups of same sizes as originals
			randomGroup1 = allSubjects[0:len(group1)]
			randomGroup2 = allSubjects[len(group1):len(group1)+len(group2)]

			# Get our component graph from random labels
			permResult = self.compareGroups(randomGroup1, randomGroup2, dataParameters)

			# Store our group result for this permutation
			result.addResult(permResult)
		
		# Return the permutation results
		return result
	
	def compare(self, group1, group2, dataParameters, iterations):

		result = ComparisonResult()

		self.cacheData(group1, group2, dataParameters)
		
		# Compare groups for actual labels
		result.actualResult = self.compareGroups(group1, group2, dataParameters)
			
		# Generate group comparisons based on random group assignments
		result.permutationResult = self.getRandomDistribution(group1, group2, dataParameters, iterations)
				
		# Calculate p values for the components of each data series
		for label, graph in result.actualResult.dataSeriesGraphs.iteritems():
			for compnent in graph.components:
				compnent.pVal = result.permutationResult.getComponentPVal(label, compnent.size())

		return result
