import mysql.connector
import io

htmlTemplate = """<!DOCTYPE HTML>
<html>
	<head>
		<title>{0} vs {1}</title>
		<meta http-equiv="content-type" content="text/html; charset=utf-8" />
		<link rel="stylesheet" href="codemirror/codemirror.css">
		<style type="text/css">			
			.CodeMirror {{
			  border: 1px solid #eee;
			  height: 100%;
			}}
		</style>
	</head>
	<body>	
		<script src="codemirror/codemirror.js"></script>
		<script src="codemirror/diff.js"></script>
		<script>
			var myCodeMirror = CodeMirror(document.body, {{
				value: "{2}",
				mode:  "diff",
				lineNumbers: true
			}});	
		</script>
	</body>
</html>"""

class DiffType:
	
	ADDED = 1
	REMOVED = 2
	UNCHANGED = 3

	def asPrefix(diffType):
		if diffType == DiffType.ADDED: 
			return "+"
		if diffType == DiffType.REMOVED: 
			return "-"
		return " "	

		
class Field:

	def __init__(self, name, sqlType):
		self.name = name
		self.sqlType =sqlType
		self.diffType = DiffType.UNCHANGED
		
	def __str__(self):
		return "field %s %s" % (self.name, self.sqlType)
		
	def __eq__(self, other):
		if type(self) == type(other):
			return self.name == other.name
		return False
		
class Table:

	def __init__(self, name):
		self.name = name
		self.fields = []
		self.diffType = DiffType.UNCHANGED

	def __str__(self):
		return "table %s" % self.name

	def __eq__(self, other):
		if type(self) == type(other):
			return self.name == other.name
		return False
		
		
oldDB = mysql.connector.connect(user='root', password='',
                              host='127.0.0.1',
                              database='openlca_beta3')

newDB = mysql.connector.connect(user='root', password='',
                              host='127.0.0.1',
                              database='openlca_beta6')

							  
oldCursor = oldDB.cursor()							  				  
newCursor = newDB.cursor() 


def readTables(cursor):
	query = "SHOW TABLES"
	cursor.execute(query)
	tables = []
	for (row) in cursor:
		table = Table(row[0])
		tables.append(table)
	tables.sort(key = lambda table: table.name)
	readFields(tables, cursor)
	return tables

	
def readFields(tables, cursor):
	for table in tables:
		query = "SHOW COLUMNS IN " + table.name
		cursor.execute(query)
		for row in cursor:
			field = Field(row[0], row[1])
			table.fields.append(field)
		table.fields.sort(key = lambda field: field.name)


def calcDiff(oldTables, newTables):
	
	oldIdx = 0
	newIdx = 0
	diffTables = []
			
	while oldIdx < len(oldTables) or newIdx < len(newTables):
		
		if oldIdx >= len(oldTables):
			newTable = newTables[newIdx]
			tagTable(newTable, DiffType.ADDED)
			diffTables.append(newTable)
			newIdx += 1
			continue
			
		if newIdx >= len(newTables):
			oldTable = oldTables[oldIdx]
			tagTable(oldTable, DiffType.REMOVED)
			diffTables.append(oldTable)
			oldIdx += 1			
			continue
			
		oldTable = oldTables[oldIdx]
		newTable = newTables[newIdx]
		
		if oldTable.name == newTable.name:
			diffTable = calcDiffTable(oldTable, newTable)
			diffTables.append(diffTable)
			newIdx += 1
			oldIdx += 1
			continue
			
		if oldTable in newTables:
			newTable = newTables[newIdx]
			tagTable(newTable, DiffType.ADDED)
			diffTables.append(newTable)
			newIdx += 1
		else:
			oldTable = oldTables[oldIdx]
			tagTable(oldTable, DiffType.REMOVED)
			diffTables.append(oldTable)
			oldIdx += 1
	
	return diffTables


def calcDiffTable(oldTable, newTable):
	
	oldFields = oldTable.fields
	newFields = newTable.fields

	oldIdx = 0
	newIdx = 0
	diffTable = Table(oldTable.name)
	diffFields = diffTable.fields
	
	while oldIdx < len(oldFields) or newIdx < len(newFields):
		
		if oldIdx >= len(oldFields):
			newField = newFields[newIdx]
			newField.diffType = DiffType.ADDED
			diffFields.append(newField)
			newIdx += 1
			continue
			
		if newIdx >= len(newFields):
			oldField = oldFields[oldIdx]
			oldField.diffType = DiffType.REMOVED			
			diffFields.append(oldField)
			oldIdx += 1			
			continue
			
		oldField = oldFields[oldIdx]
		newField = newFields[newIdx]
		
		if oldField.name == newField.name:
			if oldField.sqlType == newField.sqlType:
				diffFields.append(newField)
			else:
				# type changed
				oldField.diffType = DiffType.REMOVED
				newField.diffType = DiffType.ADDED
				diffFields.append(oldField)
				diffFields.append(newField)
			newIdx += 1
			oldIdx += 1
			continue
			
		if oldField in newFields:
			newField = newFields[newIdx]
			newField.diffType = DiffType.ADDED
			diffFields.append(newField)
			newIdx += 1
		else:
			oldField = oldFields[oldIdx]
			oldField.diffType = DiffType.REMOVED			
			diffFields.append(oldField)
			oldIdx += 1		
	
	return diffTable
	
	
def tagTable(table, diffType):
	table.diffType = diffType
	for field in table.fields:
		field.diffType = diffType
	

def writeDiff(diff, writer, compact = False):
	lineBreak = "\\n" if compact else "\n"
	for table in diff:
		tableHead = "%s %s (" %  (DiffType.asPrefix(table.diffType), table.name)
		writer.write(tableHead)
		writer.write(lineBreak)
		for field in table.fields:
			fieldText = "%s    %s [%s]" % (DiffType.asPrefix(field.diffType), 
											field.name, field.sqlType)
			writer.write(fieldText)
			writer.write(lineBreak)		
		tableFooter = "%s )" % DiffType.asPrefix(table.diffType)
		writer.write(tableFooter) 
		writer.write(lineBreak)
		writer.write(lineBreak)
			
		
oldTables = readTables(oldCursor)  
newTables = readTables(newCursor)
oldCursor.close()
newCursor.close()			  
oldDB.close()
newDB.close()

diff = calcDiff(oldTables, newTables)
writer = io.StringIO()
writeDiff(diff, writer, True)
diffText = writer.getvalue()
writer.close()

html = htmlTemplate.format("old_database_name", "new_database_name", diffText)

htmlFile = open("test.html", 'w')
htmlFile.write(html)
htmlFile.close()

  
  
  

