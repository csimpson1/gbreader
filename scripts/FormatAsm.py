import argparse
from copy import deepcopy
import os
import re
from shutil import move
import tempfile
from docutils.nodes import line

class CodeGroup:
    
    def __init__(self, numRows, maxSemicolonIdx):
        self.numRows = numRows
        self.maxSemiColonIdx = maxSemicolonIdx

class CommentGroup:
    
    def __init__(self, numRows, maxLen):
        self.numRows = numRows
        self.maxLen = maxLen
        
        self.hasTopBorder = False
        self.hasBottomBorder = False
        
        self.whiteSpaceSig = None

class AsmFormatter:
    
    def __init__(self, file, output=None, globalIndent = False):
        self.input = file
        self.output = output
        self.globalIndent = globalIndent
        
        self.codeNoComment = re.compile("^((?!;).)*$")         # Match if the line does not contain ; 
        #self.codeAndComment = re.compile("^\s*(\w+,*\s*)+;")   # Match if the line contains some alphanumeric characters, followed by a ;
        self.codeAndComment = re.compile("^\s*\w+.*;")         # Match if the line contains some alphanumeric characters, followed by a ;
        self.noCodeComment = re.compile("^\s*;")               # Match if the line contains some whitespace, followed by a ;
        self.commentBorder = re.compile("^\s*;-*;")            # Match if the line is a comment border 
        self.leadingWhiteSpace = re.compile("^([ \t]*)")       # Match just the leading whitespace of a line.
        
        self.globalLineLen = 0
        self.commentLines  = {}
        self.commentGroups = {}
        self.codeLines     = {}
        self.codeGroups    = {}
        

        
    def format_asm(self):
        """
        Format an asm file to comply with the following standards
        
        1) if a comment is preceeded by code, that comment must be indented to the global comment level
        2) If the comment is not proceeded by code, it must be surrounded like so
    
        ;-------------------;
        ; This is a comment ;
        ; nice, huh?        ;
        ;-------------------;
        
        2.1) Must start with a ;-...-;
        2.2) lines with text must start and end with a ;
        2.3) must end with a ;-...-;
        2.4) Whitespace before the leading semicolon, and after the semicolon but preceeding any text is preserved as is
              
        
        """
        
        #proc = psutil.Process()
        
        if self.output:
            outputFile = self.output
            
        else:
            inputPath = os.path.abspath(os.path.dirname(self.input))

            
            tmpFilePackage = tempfile.mkstemp(dir=inputPath)
            outputFile = tmpFilePackage[1]
            
        

        
        self._find_features(self.input)
        self._get_candidate_comment_groups()
        self._get_candidate_code_groups()

        
        with open(self.input, 'r') as f:
            with open(outputFile, 'w') as o:
                
                fNumbered = enumerate(f)
                for idx, line in fNumbered:
        
                    """
                    Rule 2 Implementation
                    """
                    
                    if idx in self.commentGroups:
                        
                        group = self.commentGroups[idx]
                        groupLine = line
                        whiteSpace = line[:line.find(';'):]
                        #Subtract 2 from the maxlength because one character is already a semicolon, one is a newline
                        borderString = whiteSpace + ';' + '-' * (group.maxLen - 2 - len(whiteSpace)) + ';\n'
                        
                        if not group.hasTopBorder:
                            o.write(borderString)
                            
                            
                        for i in range(group.numRows):
                            
                            if not self.is_comment_formatted(groupLine):
                                groupLine = self.format_comment(groupLine, group.maxLen)
                            
                            o.write(groupLine)
                            
                            if i < group.numRows - 1:
                                try:
                                    idx, groupLine = fNumbered.__next__()
                                
                                #The last line of the file was a part of the comment group
                                #So, we can end this function here
                                except StopIteration as e:
                                    
                                    if not group.hasBottomBorder:
                                        o.write(borderString) 
                                    
                                    f.close()
                                    o.close()
    
                                    
                                    if not self.output:
                                        self.rename_and_remove_tempfile(outputFile)
                                    
                                    return
                                
                        if not group.hasBottomBorder:
                            o.write(borderString)
                        line = groupLine
                        
                        continue

                    
                    """
                    Rule 1 Implementation
                    """
                    
                    if idx in self.codeGroups:
                        
                        cGroup = self.codeGroups[idx]
                        cGroupLine = line
                        
                        for i in range(cGroup.numRows):
                    
                            match = re.search(self.codeAndComment, cGroupLine)
                            if match and not self.is_code_formatted(cGroupLine, cGroup):
                                
                                indentType = self.globalLineLen if self.globalIndent else cGroup.maxSemiColonIdx
                                cGroupLine = self.pad_line_with_spaces(cGroupLine, indentType)
                            
                            o.write(cGroupLine)
                                
                                
                            if i < cGroup.numRows - 1:
                                try:
                                    idx, cGroupLine = fNumbered.__next__()
                                
                                except StopIteration as e:
                                    
                                    #get rid of noeol warnings in vi
                                    o.write('\n')
                                    
                                    f.close()
                                    o.close()
            
                                    if not self.output:
                                        self.rename_and_remove_tempfile(outputFile)
                                        return 
                                    
                            

                #get rid of noeol warnings in vi
                o.write('\n')
        
        if not self.output:
            self.rename_and_remove_tempfile(outputFile)
            
        return
    
    def rename_and_remove_tempfile(self, tf):
        path = os.path.abspath(self.input)
        move(os.path.abspath(tf), path)
        
    
    def pad_line_with_spaces(self, line, indent):
        idx = line.index(';')
        code = line[:idx]
        code += " " * (indent - len(code))
        line = code + line[idx:]
        
        return line
    
    def format_comment(self, line, length):
        
        offset = length - len(line)
        return  line[:-1] + (offset * ' ') + ';\n'
    
    def is_code_formatted(self, line, cGroup):
        """
        Identify if a line of code with a comment has possibly already been formatted by this tool.
        
        This function looks to see if the semicolon on a given line is at group.maxLen + 1. If so,
        we assume that this string has already been formatted, and skip it
        """
        
        semiColonIdx = line.find(';')
        
        return semiColonIdx == cGroup.maxSemiColonIdx
        
    def is_comment_formatted(self, line):
        """
        Identifies if a comment has possibly already been formatted by this tool
        
        This functions checks for the existence of a second semicolon in a comment line. If this exists
        it assumes that it has already been formatted by this tool.
        
        This also lets users escape this comment formatting, by using a double semicolon instead of just one
        """
        semiColonIdx = line.find(';')
        secondSCIdx = line.find(';', semiColonIdx + 1)
        
        return secondSCIdx != -1
        
        
    
    def _find_features(self, file):
        """
        Finds all comment groups in the file, as well as the maximum length of all lines containing code
        
        . A comment group will look like
        
        ; Something 
        ; like
        ; this
    
        Identifying and formatting comment groups
        
        All ; characters in a comment group must be at the same indent level. Different
        indent levels will denote different comment groups
        
        A comment group is considered ended when
        1) The next line contains code
        2) The next line contains a differently indented comment group

        """    
        
        with open(file, 'r') as f:
            

            for idx, line in enumerate(f):
                
                """
                Start by checking for comment groups because the logic works nicely. If its a comment, note down the location.
                If not, then we can check for the length
                """
                
                #TODO: test this out
                #lineEscaped = re.escape(line)
                
                match = re.search(self.noCodeComment, line)
                if match:
                    
                    #whitespace = re.match(self.leadingWhiteSpace, line)
                    self.commentLines[idx] = line
                        
                
                length = 0
                
                match = re.search(self.codeNoComment, line)
                
                if match:
                    length = len(line.rstrip())
                    self.codeLines[idx] = line
                
                match = re.search(self.codeAndComment, line)    
                if match:
                    length = len(line.split(';')[0].rstrip()) # Code will be anything before the first ; 
                    self.codeLines[idx] = line

                if length > self.globalLineLen:
                    self.globalLineLen = length
        
        
        #Add one extra space so that the semicolon is not immediately against the end of the code
        self.globalLineLen += 1

    def _get_candidate_comment_groups(self):
        
        """
        Scan through the list of comment lines and construct a dictionary of CommentGroup objects
        """
        indices = list(self.commentLines.keys())
        indices.sort()
        
        startIdx = indices[0]
        prevIdx = indices[0]
        prevLine = self.commentLines[prevIdx]
        group = CommentGroup(1,len(prevLine))
        prevWhiteSpaceSig = re.match(self.leadingWhiteSpace, prevLine).group()
        
        match = re.match(self.commentBorder, prevLine)
        
        if match:
            group.hasTopBorder = True

        
        for i in indices[1:]:
            currentLine = self.commentLines[i]
            whiteSpaceSig = re.match(self.leadingWhiteSpace, currentLine).group()
            
            
            if i == prevIdx + 1 and whiteSpaceSig == prevWhiteSpaceSig:
                
                """
                The lines are consecutive and have the same amount of whitespace. So we can add this line
                to the current commentGroup, and update the maximum line length if necessary
                """
                
                group.numRows += 1
                currentLineLen = len(currentLine)
                
                if currentLineLen > group.maxLen:
                    
                    group.maxLen = currentLineLen
                
                prevIdx = i
                prevLine = currentLine
                
                continue
            
            """
            Either we skipped a line, indicating that there was some code in the original document
            or we found a comment that has a different amount of whitespace. This means we've
            started a new 
            """
            
            bottomBorder = re.match(self.commentBorder, prevLine)
            
            # The second clause here rules out a degenerate case: one row in a comment that is just a border. By convention, we'll consider 
            # this the top border in a comment group
            if bottomBorder and not (group.numRows == 1 and group.hasTopBorder):
                group.hasBottomBorder = True
                
            self.commentGroups[startIdx] = deepcopy(group)
            
            startIdx = i
            group = CommentGroup(1, len(currentLine))
            
            #Started a new group, so see if the line is a border
            match = re.match(self.commentBorder, prevLine)
            
            if match:
                group.hasTopBorder = True
        
            
            prevIdx = i
            prevLine = currentLine
            prevWhiteSpaceSig = whiteSpaceSig
            
        if startIdx not in self.commentGroups:
            
            #We exited before we were able to add the group to the list of groups.
            #Means that the check to see if the last line was a border was not performed
            #so do that here.
            
            match = re.match(self.commentBorder, prevLine)
            
            if match:
                group.hasBottomBorder = True
                
            self.commentGroups[startIdx] = deepcopy(group)
        
        #TODO: Remove this    
        pass
                
    def _get_candidate_code_groups(self):
        
        indices = list(self.codeLines.keys())
        indices.sort()
        
        startIdx = indices[0]
        prevIdx = indices[0]
        prevLine = self.codeLines[prevIdx]
        group = CodeGroup(1,prevLine.find(';'))
        prevWhiteSpaceSig = re.match(self.leadingWhiteSpace, prevLine).group()
        
        for i in indices[1:]:
            
            currentLine = self.codeLines[i]
            whiteSpaceSig = re.match(self.leadingWhiteSpace, currentLine).group()
            
            """
            The second or clause cover the case where we have a blank line between some lines of code that 
            are at the same indent level, like
            
            ld a, b
            xor a
            
            bit 0, [rLCDC]
            
            Leading whitespace is the main criteria for determining blocks of code
            """
            
            if i == prevIdx + 1 and (whiteSpaceSig == prevWhiteSpaceSig or whiteSpaceSig == '\n'):
                
                group.numRows += 1
                currentLineIdx = currentLine.find(';')
                
                if currentLineIdx > group.maxSemiColonIdx:
                    group.maxSemiColonIdx = currentLineIdx
                
                prevIdx = i
                prevLine = currentLine
                
                continue
            
            """
            Either we skipped a line, or the whitespace signature changed. This means the current group
            is completed.
            """
            
            self.codeGroups[startIdx] = deepcopy(group)
            
            startIdx = i
            group = CodeGroup(1, currentLine.find(';'))
            
            prevIdx = i
            prevLine = currentLine
            prevWhiteSpaceSig = whiteSpaceSig
            
        if startIdx not in self.codeGroups:
            self.codeGroups[startIdx] = group
            

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Format an ASM file.')
    parser.add_argument('input', help='Location of the ASM file to be imported')
    parser.add_argument('-o', '--output', help='Location of an output ASM file')
    parser.add_argument('-g', '--global_indent', action="store_true", help='Adjust comments at the end of code lines to a global indent level')
    
    args = parser.parse_args()
    formatter = AsmFormatter(args.input, args.output, args.global_indent)
    formatter.format_asm()
    
    
    