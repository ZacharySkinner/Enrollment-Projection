import os
import networkx as nx
import pandas as pd
import re
from colorama import Fore, Back, Style
from pyvis.network import Network
import ast
import sys


sys.path.append(sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))))

# from datastructures.college import College
# from datastructures.course import create_courses
# from datastructures.department import Department
# from datastructures.program import DegreeType
# from datastructures.program_uGrad import build_program
# from helper_functions.student_objects import create_student_objects_from_csv, filter_students_by_program
# from helper_functions.traverse import traverse



class DAGBuilder:
    def __init__(self, program_name, subgraphs, required_courses, course_database, offered_file_path):
        self.from_program=set()
        self.from_prereq=set()
        self.program_name = program_name
        self.subgraphs = subgraphs
        self.required_courses = required_courses
        self.course_database = course_database
        self.Graph = nx.DiGraph()  # Directed graph for the courses
        self.special_nodes = {}  # Dictionary to hold special nodes (e.g., Start, Graduation)
        self.not_in_database=set()
        self.colors=["red","purple","blue","cyan","green","orange","purple","black","pink",]
        self.color_index=0
        self.cluster_name=""
        self.offered=self.get_offered(offered_file_path)
        test=1
    def get_offered(self,path):
        offered_df = pd.read_csv(path)
        course_ids = set(offered_df['SUBJ_COU_NBR'])
        return course_ids
    #builds full graph including all subgraphs
    def build_full_graph(self):
        self.add_node("Start","start",-1,-1,-1,"")
        self.add_node("Graduation","end",-1,-1,-1,"")
        if len(self.subgraphs)==len(self.required_courses):
            for i in range(len(self.subgraphs)):
                self.color_index+=1
                self.build_subgraph(self.subgraphs[i],self.required_courses[i])


        else:
            print(Fore.RED +Fore.RED +"Number of subgraphs does not match number of required course lists"+Style.RESET_ALL)

    #Builds subgraph using course list
    def build_subgraph(self,subgraph,course_list,start="Start",finish="Graduation"):
        #initializes start and finish nodes for subgraph
        start_subgraph_node=f"Start_{subgraph}"
        finish_subgraph_node=f"Finish_{subgraph}"
        self.add_node(start_subgraph_node,"subgraphnode",-1,-1,-1,"")
        self.add_node(finish_subgraph_node,"subgraphnode",-1,-1,-1,"")
        self.add_edge(start,start_subgraph_node)
        self.add_edge(finish_subgraph_node,finish)

        #loops through all classes associated with subgraph and adds them to the graph
        if "credits"in course_list[0]:
            course_list=[course_list]
        for course in course_list:
            self.add_course(course,subgraph)
        
        #connects all nodes in subgraph that currently point at nothing and point them at the subgraph_finish node 
        nodes=list(self.Graph.nodes)
        for node in nodes:
            if (len(self.Graph.adj[node]) == 0) and (subgraph in node) :
                    self.add_edge(node,finish_subgraph_node)

    #Adds a individual course to graph, recurssivly adds any prereqs that are not on graph yet
    #Returns name of node added as string
    def add_course(self,course,subgraph):
        #defines name of node being added


        #checks if the node being added is a special case node 
        if type(course)==list:
            special_node=self.add_special_node(course,subgraph)
            return special_node
        elif type(course)==dict:
            course=[course]
            special_node=self.add_special_node(course,subgraph)
            return special_node
        

        course_id_result=self.get_course_ids(course)

        if len (course_id_result):
            course_id=course_id_result[0]
            if "take" in course:
                course=course_id
            else:
                course_id=course
        else:
            course_id=None
        course_node=f"{subgraph}_{course}"
        
        #checks if node is already on graph
        if self.Graph.has_node(course_node):
            return course_node
        else:
            credit_value=self.get_credits(course_id)
            completions_needed=1
            self.add_node(course_node,"course",completions_needed,-1,credit_value,course_id)
        #Get prereqs for node if there is no prereqs connect current node to start
        course_prereqs=self.get_course_prereqs(course,course_node)
        if len(course_prereqs) == 0:
            start_node=f"Start_{subgraph}"
            self.add_edge(start_node,course_node)
            return course_node
        
        # Loop through prereqs and add them to graph
        for prereq in course_prereqs:
            prereq_node=self.add_course(prereq,subgraph)
            self.add_edge(prereq_node,course_node)
        return course_node
   
    def get_reqs_from_list(self,lyst,resultss):
        results=resultss
        for req in lyst:
            if type(req)==list:
                self.get_reqs_from_list(req,results)
            else:
                id=self.get_course_ids(req)
                if id:
                    results.append(id[0])
        return results

    def add_range(self,range_string,subgraph,credit_node):
        df = pd.read_csv(self.course_database)
        prefix_regex= r'\w{2,4}'
        range_regex = r'\d{3}'
        num_range = re.findall(range_regex,range_string)
        prefix = re.findall(prefix_regex,range_string)
        lower=int(num_range[0])
        upper=int(num_range[1])
        if prefix[0] == "ANY":
            course_id_node=self.add_course(range_string,subgraph)
            self.add_edge(course_id_node,credit_node)
        else:
            for num in range (lower,upper):
                course=f"{prefix[0]} {num}"
                filtered = df[df['Course ID'] == course]
                if len(filtered)!=0:
                    course_id = str(filtered['Course ID'].iloc[0])
                    course_id_node=self.add_course(course_id,subgraph)
                    self.add_edge(course_id_node,credit_node)

    def build_cluster(self,cluster_dict,subgraph):
        cluster_name="CLUSTER"
        self.cluster_name=cluster_name
        cluster_node=f"{subgraph}{self.cluster_name}"
        start_subgraph_node=f"Start_{subgraph}"
        self.add_node(cluster_node,"cluster",cluster_dict=cluster_dict["rules"])

        
        area_count=0
        for area in cluster_dict:
            if area != "rules":
                area_count+=1
                area_node=f"Finish_{subgraph}_{self.cluster_name}_area_{area_count}"
                area_reqs=self.get_reqs_from_list(cluster_dict[area],[])
                self.add_node(node=area_node,node_type="area",req_list=area_reqs)
                self.add_edge(area_node,cluster_node)
                for req in cluster_dict[area]:
                    name=self.add_course(req,subgraph)
                    self.add_edge(name,area_node)
        self.cluster_name=""
        pass

    #Adds a node that itself is not a class
    def add_special_node(self,courses,subgraph):
        if type(courses[0]) == dict:
            return self.build_cluster(courses[0],subgraph)
        special_case=courses[0]
        credits=-1
        credit_regex= r'\d+'
        result=re.search(credit_regex,special_case)
        if result != None:
            credits=result[0]
            node_type="creditsneeded"
        else:
            node_type="or"
        if special_case not in self.special_nodes:
            self.special_nodes[special_case]=1
        else:
            self.special_nodes[special_case]+=1

        special_node=f"{subgraph}{self.cluster_name}_{special_case}_{self.special_nodes[special_case]}"
        self.add_node(node=special_node,node_type=node_type,completion_credits_needed=1,credits=credits,credits_needed=credits)

        for i in range(1,len(courses)):
            course=courses[i]
            if "-" in course:
                self.add_range(course,subgraph,special_node)
            else:
                course_node=self.add_course(course,subgraph)           
                self.add_edge(course_node,special_node)
                self.Graph.nodes[special_node]['required_credits'] = credits
        return special_node
    
    #Returns list of courses prereqs
    def get_course_prereqs(self,course,course_node):
        #put prereq into string
        df = pd.read_csv(self.course_database)
        filtered = df[df['Course ID'] == course]
        if len(filtered)==0:
            self.Graph.nodes[course_node]["predictable"]=False
            self.not_in_database.add(course)
            return []
        prereq_string = str(filtered['PreReq'].iloc[0])
        prereq_string=prereq_string.replace("and",",")
        prereq_string=prereq_string.replace(".",",")
        or_list=[]
        if ":" in prereq_string:
            indexx=prereq_string.index(":")
            string_of_ands=prereq_string[0:indexx]
            string_of_ors=prereq_string[indexx:]
        elif "or" in prereq_string:
            indexx=prereq_string.index("or")-10
            if indexx<0:
                indexx=0
            string_of_ands=prereq_string[0:indexx]
            string_of_ors=prereq_string[indexx:]
        else:
            string_of_ands=prereq_string
            string_of_ors=""
                    

        or_result=self.get_course_ids(string_of_ors)
        if len(or_result)==0:
            or_list=[]
        else:
            or_list=["or"]
            for i in or_result:
                or_list.append(i)
        results=self.get_course_ids(string_of_ands)
        

        if len(or_list)>0:
            results.append(or_list)

        return results

    def add_node(self,node,node_type,completion_credits_needed=-1,credits_needed=-1,credits=-1,course_id="",cluster_dict=None,predictable=True,req_list=None):
        node_types=["start","end","or","course","creditsneeded","subgraphnode","cluster","area"]
        if node_type not in node_types:
            print(Fore.RED +f"Invalid Node Type!! Cant use: ##{node_type}## you must use one of the following node types:{node_types}"+Style.RESET_ALL)
        if self.is_offered(course_id) == False:
            predictable = False
        self.Graph.add_node(node,node_type=node_type,completion_credits_needed=completion_credits_needed,credits_needed=credits_needed,credits=credits,course_id=course_id,color=self.colors[self.color_index],cluster_dict=cluster_dict,predictable=predictable,req_list=req_list)

    def is_offered(self,course):
        return course in self.offered

    def add_edge(self,node1,node2):
        
        not_added=[]
        if node1 not in self.Graph.nodes():
            not_added.append(node1)
        if node2 not in self.Graph.nodes():
            not_added.append(node2)
        if (node1 == node2) or (node2 in self.Graph.predecessors(node1)):return None
        if not_added==[]:
            self.Graph.add_edge(node1,node2)
        else:
            self.Graph.add_edge(node1,node2)
            
    def get_credits(self,course_id):
        df = pd.read_csv(self.course_database)
        filtered = df[df['Course ID'] == course_id]
        if len(filtered)==0:
            self.not_in_database.add(course_id)
            return -1
        else:
            credit_value_str = str(filtered['Credits'].iloc[0])
            credit_value_regex= r'\w+'
            result = re.match(credit_value_regex,credit_value_str)
            if result:
                if result.group() == 'nan':
                    credit_value=1
                else:
                    credit_value=int(result.group())
            else:
                credit_value=-1
            return credit_value

    def get_course_ids(self,string_containing_course_id):
        courseid_regex= r'[A-Z]{2,5} \d{2,5}\w?'
        result = re.findall(courseid_regex,string_containing_course_id)
        return result
    
    def save_graph(self):
            base_dir=os.path.dirname(os.path.abspath(__file__))
            dotfile_path = os.path.join(base_dir,"..", 'dag_files', 'dot_files',f"{self.program_name}.dot")
            htmlfile_path = os.path.join(base_dir,"..", 'dag_files', 'html_files',f"{self.program_name}.html")

            #save graph to dot file
            nx.drawing.nx_pydot.write_dot(self.Graph,dotfile_path)

            #save to HTML
            net = Network(notebook=True, directed=True, cdn_resources='remote')
            net.from_nx(self.Graph)
            net.show(htmlfile_path)  #DAGAutomation\HTML_FILES



def make_all_graphs(database_path, program_requirment_path, offered_path):
    df = pd.read_csv(program_requirment_path)
    # Dictionary to store graphs with program names as keys
    list_of_missing=set()
    from_program=set()
    from_pre=set()
    # Iterate through each program in the dataset
    for i, row in df.iterrows():

        total_requiredCourses = []
        subgraphs = []
        program_name = row["Program"]

        # Check if the program is an undergraduate program
        if True:
            print(f"starting {program_name}")
            possible_subgraphs=["prereqToMajorList","reqGenEdsList","majorCommonCoreList","ChooseThesisCapstone","majorRestrictiveElectivesList","majorUnrestrictedElectivesList"]
            if not os.path.exists(database_path) or not os.path.exists(program_requirment_path) or not os.path.exists(off_path):
                raise FileNotFoundError("Missing CSVs. See Data/InputData/README.md for required schema and example files.")

            # Iterate through each possible subgraph
            for subgraph in possible_subgraphs:
                required_course_list=row[subgraph]
                
                # Convert string representations of lists into actual lists
                if type(required_course_list) == str:
                    required_course_list=ast.literal_eval(required_course_list)

                # Add non-empty course lists to the subgraphs and total_requiredCourses
                if required_course_list!=[]:
                    if type(required_course_list) == list:
                        subgraphs.append(subgraph)
                        total_requiredCourses.append(required_course_list)

            # Create a DAGBuilder instance for the program
            test = DAGBuilder(program_name, subgraphs, total_requiredCourses,database_path,offered_path)
            
            # Build the graph
            test.build_full_graph()
            list_of_missing=list_of_missing.union(test.not_in_database)
            from_pre=from_pre.union(test.from_prereq)
            from_program=from_program.union(test.from_program)
            test.save_graph()

    return [list_of_missing,list(list_of_missing),from_program]



if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.abspath(__file__))  # Get the directory of the current file
    database_path = os.path.join(base_dir,"..", 'Data', 'InputData','cleaned_course_list_FIX.csv')  # Join the components to form the path
    program_requirment_path = os.path.join(base_dir,"..",'Data', 'InputData','Batch3.1.csv')  # Join the components to form the path
    off_path=os.path.join(base_dir,"..",'Data', 'InputData','Offered_Courses.csv')
    missing = make_all_graphs(database_path,program_requirment_path,offered_path=off_path)
    no_spaces=[]
    ranges=[]
    courses=[]
    leadingwhite=[]
    other=[]
    rangesbad=[]
    for i in missing[1]:
        if i == None:
            pass
        elif " " not in i:
            no_spaces.append(i)
        elif i[0] == " " or i[len(i)-1]==" ":
            leadingwhite.append(i)
        elif " - " in i:
            ranges.append(i)
        elif len(i)>12:
            other.append(i)
        elif "-" in  i:
            rangesbad.append(i)
        else:
            courses.append(i)
    print("Courses missing from course data base:")
    print(f"\033[35mno spaces: {no_spaces}\033[0m")
    print(f"White Space: {leadingwhite}\033[0m")
    print(f"\033[34mranges: {ranges}\033[0m")
    print(f"\033[36mrangesbad: {rangesbad}\033[0m")
    print(f"\033[32mother: {other}\033[0m")
    courses.sort()
    print(f"\033[31mcourses: {courses}\033[0m")
    course_set=set(courses)
    program_missing=course_set.intersection(missing[2])
    pre_missing=course_set.difference(program_missing)
