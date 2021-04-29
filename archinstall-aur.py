import archinstall

def install_aur_packages(*packages):
	if len(packages) == 1 and type(packages[0]) == list:
		packages = packages[0]
	elif len(packages) == 1 and type(packages[0]) == str:
		packages = packages[0].split(' ')

	print('Installing AUR packages:', packages)

archinstall.install_aur_packages = install_aur_packages
