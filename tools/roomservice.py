#!/usr/bin/env python
import os
import sys
import urllib2
import json
from xml.etree import ElementTree

product = sys.argv[1];
device = product[product.index("_") + 1:]
print "Device %s not found. Attempting to retrieve device repository from CyanogenMod Github (http://github.com/CyanogenMod)." % device

repositories = []

page = 1
while True:
    result = json.loads(urllib2.urlopen("http://github.com/api/v2/json/repos/show/CyanogenMod?page=%d" % page).read())
    if len(result['repositories']) == 0:
        break
    repositories = repositories + result['repositories']
    page = page + 1

for repository in repositories:
    repo_name = repository['name']
    if repo_name.startswith("android_device_") and repo_name.endswith("_" + device):
        print "Found repository: %s" % repository['name']
        manufacturer = repo_name.replace("android_device_", "").replace("_" + device, "")
        
        try:
            lm = ElementTree.parse(".repo/local_manifest.xml")
            lm = lm.getroot()
        except:
            lm = ElementTree.Element("manifest")
        
        for child in lm.getchildren():
            if child.attrib['name'].endswith("_" + device):
                print "Duplicate device '%s' found in local_manifest.xml." % child.attrib['name']
                sys.exit()

        repo_path = "device/%s/%s" % (manufacturer, device)
        project = ElementTree.Element("project", attrib = { "path": repo_path, "remote": "github", "name": "CyanogenMod/%s" % repository['name'] })
        lm.append(project)
        
        raw_xml = ElementTree.tostring(lm)
        raw_xml = '<?xml version="1.0" encoding="UTF-8"?>\n' + raw_xml

        f = open('.repo/local_manifest.xml', 'w')
        f.write(raw_xml)
        f.close()

def fetch_dependencies(repo_path):
    print 'Looking for dependencies'
    dependencies_path = repo_path + '/cm.dependencies'
    syncable_repos = []

    if os.path.exists(dependencies_path):
        dependencies_file = open(dependencies_path, 'r')
        dependencies = json.loads(dependencies_file.read())
        fetch_list = []

        for dependency in dependencies:
            if not is_in_manifest("CyanogenMod/%s" % dependency['repository']):
                fetch_list.append(dependency)
                syncable_repos.append(dependency['target_path'])

        dependencies_file.close()

        if len(fetch_list) > 0:
            print 'Adding dependencies to manifest'
            add_to_manifest(fetch_list)
    else:
        print 'Dependencies file not found, bailing out.'

    if len(syncable_repos) > 0:
        print 'Syncing dependencies'
        os.system('repo sync %s' % ' '.join(syncable_repos))

def has_branch(branches, revision):
    return revision in [branch['name'] for branch in branches]

if depsonly:
    repo_path = get_from_manifest(device)
    if repo_path:
        fetch_dependencies(repo_path)
    else:
        print "Trying dependencies-only mode on a non-existing device tree?"

    sys.exit()

else:
    for repository in repositories:
        repo_name = repository['name']
        if repo_name.startswith("android_device_") and repo_name.endswith("_" + device):
            print "Found repository: %s" % repository['name']
            
            manufacturer = repo_name.replace("android_device_", "").replace("_" + device, "")
            
            default_revision = get_default_revision()
            print "Default revision: %s" % default_revision
            print "Checking branch info"
            githubreq = urllib2.Request(repository['branches_url'].replace('{/branch}', ''))
            add_auth(githubreq)
            result = json.loads(urllib2.urlopen(githubreq).read())
            
            repo_path = "device/%s/%s" % (manufacturer, device)
            adding = {'repository':repo_name,'target_path':repo_path}
            
            if not has_branch(result, default_revision):
                found = False
                if os.getenv('ROOMSERVICE_BRANCHES'):
                    fallbacks = filter(bool, os.getenv('ROOMSERVICE_BRANCHES').split(' '))
                    for fallback in fallbacks:
                        if has_branch(result, fallback):
                            print "Using fallback branch: %s" % fallback
                            found = True
                            adding['branch'] = fallback
                            break
                            
                if not found:
                    print "Default revision %s not found in %s. Bailing." % (default_revision, repo_name)
                    print "Branches found:"
                    for branch in [branch['name'] for branch in result]:
                        print branch
                    print "Use the ROOMSERVICE_BRANCHES environment variable to specify a list of fallback branches."
                    sys.exit()

            add_to_manifest([adding])

            print "Syncing repository to retrieve project."
            os.system('repo sync %s' % repo_path)
            print "Repository synced!"

            fetch_dependencies(repo_path)
            print "Done"
            sys.exit()

print "Repository for %s not found in the CyanogenMod Github repository list. If this is in error, you may need to manually add it to your local_manifest.xml." % device
