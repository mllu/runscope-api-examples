import json
import requests
import os
import sys
import inspect
import pprint
import click

pp = pprint.PrettyPrinter(indent=4)

# mapping between test name and id
"""
sample global_dict
{
    'google': '45a0e3b6-a8ab-4645-9657-028979e50e3f'
}
"""
global_test_id_dict = {}

# Global dictionary to keep local reference of account name, bucket key
# headers for authentication, base API URL and test data
"""
sample global_dict
{
    'headers': {'Content-type': 'application/json', 'Authorization': u'Bearer ff2e42e6-86a6-430d-8f86-3d5886eeaac6'}).
    'bucket_key': u'123456789',
    'base_url': 'https://api.runscope.com',
    'name': 'Foo Bar',
    'tests': {
        'my_test': {
            'test_id': 'dd337690-88a4-442a-978d-7703f79c3ac9',
            'content': JSON_DUMP_TEST
        }
    }
}
"""
global_dict = {}


# Retrieve name from account resource
# https://www.runscope.com/docs/api/account
def get_account_info():
    j = _api_get_request("/account", 200)
    global_dict["name"] = j["name"]
    print "\nHello %s.\n" % global_dict["name"]


# Retrieves list of buckets for the authed account
# https://www.runscope.com/docs/api/buckets#bucket-list
def get_bucket_list():
    return _api_get_request("/buckets", 200)


# Bucket selection (user input from terminal)
def select_bucket():
    get_account_info()
    buckets = get_bucket_list()

    for x in range(0, len(buckets)):
        print "%s - %s (%s)" % (x, buckets[x]["name"], buckets[x]["key"])

    selection = -1
    while selection < 0 or selection > len(buckets) - 1:
        selection = input("\nSelect destination bucket for the new test: ")

    global_dict["bucket_key"] = buckets[selection]["key"]


# Retrieves list of tests for given bucket
# https://www.runscope.com/docs/api/tests#list
def get_test_list(bucket_key=None):
    if not bucket_key:
        return
    return _api_get_request("/buckets/%s/tests" % bucket_key, 200)


def scan_tests():
    tests = get_test_list(global_dict["bucket_key"])
    for test in tests:
        global_test_id_dict[test.get("name")] = test.get("id")
    # pp.pprint(global_test_id_dict)


# Read and validate test from JSON file
def read_test_files(input_dir=None):
    if not input_dir:
        return
    global_dict["tests"] = {}
    for root, dirs, test_files in os.walk(input_dir):
        for test in test_files:
            try:
                # Open and read the file
                f = open(root + '/' + test, "r")
                t = f.read()
                j = json.loads(t)

                # Trigger a KeyError exception if a test name doesn"t exist
                j["name"] = j["name"]
                global_dict["tests"][test] = {
                    'test_id': global_test_id_dict.get(j['name'])
                }
                data = {
                    'name': j["name"],
                    'description': j['description'],
                    'steps': j['steps']
                }
            except IOError as e:
                sys.exit("\nI/O error({0}): {1}\n".format(e.errno, e.strerror))
            except ValueError:
                sys.exit("\nInvalid JSON in file %s\n" % sys.argv[1])
            except KeyError:
                sys.exit("\nInvalid test definition JSON in file %s: Test name is required.\n" % sys.argv[1])

            global_dict["tests"][test]['content'] = json.dumps(data)


# Create tests with API
# https://www.runscope.com/docs/api/tests#create
def create_tests():
    for name, test in global_dict["tests"].iteritems():
        content = test['content']
        data = _api_post("/buckets/%s/tests" % global_dict["bucket_key"], content, 201)
        print "\nNew test %s created.\n" % name
        # pp.pprint(data)


# Modify tests with API
# https://www.runscope.com/docs/api/tests#modifying
def modify_tests():
    for name, test in global_dict["tests"].iteritems():
        # for k, v in test.iteritems():
        #     print 'k:', k
        #     print 'v:', v
        test_id = test['test_id']
        content = test['content']
        path = "/buckets/%s/tests/%s" % (global_dict["bucket_key"], test_id)
        data = _api_put(path, content, 201)
        print "\nTest %s modified.\n" % name
        # pp.pprint(data)


# Delete tests with API
# https://www.runscope.com/docs/api/tests#delete
def delete_tests():
    for name, test in global_dict["tests"].iteritems():
        test_id = test['test_id']
        path = "/buckets/%s/tests/%s" % (global_dict["bucket_key"], test_id)
        is_deleted = _api_delete(name, path, 204)
        if is_deleted:
            print "\nTest %s deleted.\n" % name


# Execute HTTP GET request
def _api_get_request(path, status):
    r = requests.get("%s/%s" % (global_dict["base_url"], path), headers=global_dict["headers"])
    if r.status_code != status:
        _api_error_exit(r.status_code)
    return (json.loads(r.text))["data"]


# Execute HTTP POST request
def _api_post(path, data, status):
    r = requests.post("%s/%s" % (global_dict["base_url"], path), data=data, headers=global_dict["headers"])
    if r.status_code != status:
        _api_error_exit(r.status_code)
    return (json.loads(r.text))["data"]


# Execute HTTP PUT request
def _api_put(path, data, status):
    # print ("url: \n%s/%s\n" % (global_dict["base_url"], path))
    # print "body:\n"
    # pp.pprint(json.loads(data))
    r = requests.put("%s/%s" % (global_dict["base_url"], path), data=data, headers=global_dict["headers"])
    if r.status_code != status:
        _api_error_exit(r.status_code)
    return (json.loads(r.text))["data"]


# Execute HTTP DELETE request
def _api_delete(name, path, status):
    # print ("url: \n%s/%s\n" % (global_dict["base_url"], path))
    r = requests.delete("%s/%s" % (global_dict["base_url"], path), headers=global_dict["headers"])
    if r.status_code != status:
        print 'Invalid test %s with status %d' % (name, r.status_code)
        return False
        # _api_error_exit(r.status_code)
    return True


# Exits on API error, displaying status code and function
# name where error occurred.
def _api_error_exit(status_code):
    sys.exit("API error - HTTP status code %s in %s" % (status_code, inspect.stack()[1][3]))


@click.command()
@click.argument('input_dir')
@click.option('--create/--no-create', default=False)
@click.option('--delete', is_flag=True)
def main(input_dir, create, delete):
    with open("config.json") as config_file:
        config = json.load(config_file)

    global_dict["headers"] = {"Authorization": "Bearer %s" % config["runscope"]["access_token"],
                              "Content-type": "application/json"}
    global_dict["base_url"] = "https://api.runscope.com"

    select_bucket()
    scan_tests()
    read_test_files(input_dir)
    # for kk, vv in global_dict.iteritems():
    #     if kk == 'tests':
    #         for name, test in vv.iteritems():
    #             print name
    #             for k, v in test.iteritems():
    #                 if k == 'test_id':
    #                     print 'test_id: %s\n' % v
    #                 else:
    #                     print k + ':'
    #                     pp.pprint(v)
    #     else:
    #         print(kk, ':', vv)
    if delete:
        delete_tests()
    else:
        if create:
            create_tests()
        else:
            modify_tests()
    sys.exit()


if __name__ == "__main__":
    main()
