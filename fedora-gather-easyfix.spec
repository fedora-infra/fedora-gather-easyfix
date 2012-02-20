Name:           fedora-gather-easyfix
Version:        0.1.0
Release:        1%{?dist}
Summary:        Gather easyfix tickets across fedorahosted projects

License:        GPLv2+
URL:            https://fedorahosted.org/fedora-gather-easyfix/
Source0:        fedora-gather-easyfix-0.1.0.tar.gz
BuildArch:      noarch

Requires:       python-jinja2

%description
The aims of this project is to offer a simple overview of where help
is needed for people coming to Fedora.

There are a number of project hosted on  fedorahosted.org which are
participating in this process by marking tickets as 'easyfix'.
fedora-gather-easyfix find them and gather them in a single place.

A new contributor can thus consult this page and find a place/task
she/he would like to help with, contact the person in charge and get
started.

%prep
%setup -q

%build
%{__python} setup.py build

%install
rm -rf $RPM_BUILD_ROOT
%{__python} setup.py install -O1 --skip-build --root $RPM_BUILD_ROOT

%files
%doc LICENSE README
%{python_sitelib}/*
%{_bindir}/gather_easyfix.py
%dir %{_sysconfdir}/%{name}
%config(noreplace) %{_sysconfdir}/%{name}/template.html

%changelog
* Mon Feb 20 2012 Pierre-Yves Chibon <pingou@pingoured.fr> - 0.1.0-1
- Initial packaging for Fedora
