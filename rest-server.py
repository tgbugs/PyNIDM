from flask import Flask, request
from flask_restful import Resource, Api
import glob
from nidm.experiment.tools.rest import RestParser
from flask_cors import CORS

def getTTLFiles():
    files = []
    for filename in glob.glob('/opt/project/ttl/**/*.ttl', recursive=True):
        files.append(filename)
    return files

class NIDMRest(Resource):
    def get(self, all):

        query_bits = []
        for a in request.args.keys():
            query_bits.append("{}={}".format(a, request.args.get(a)))
        query = "&".join(query_bits)

        files = getTTLFiles()
        if len(files) == 0:
            return ({'error' : 'No NIDM files found. You may need to add NIDM ttl files to ~/PyNIDM/ttl'})
        return restParser(files, "{}?{}".format(all,query), 5 )

class Instructions(Resource):
    def get(self):
        return ({'message' : 'See instructions at PyNIDM/docker/README.md'})



app = Flask(__name__)
CORS(app)
api = Api(app)
api.add_resource(Instructions, '/')
api.add_resource(NIDMRest, '/<path:all>')

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')