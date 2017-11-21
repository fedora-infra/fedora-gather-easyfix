Name:           fedora-gather-easyfix
Version:        0.1.1
Release:        9%{?dist}
Summary:        Gather easyfix tickets across fedorahosted projects

License:        GPLv2+
URL:            https://pagure.io.org/fedora-gather-easyfix/
Source0:        https://releases.pagure.org/fedora-gather-easyfix/%{name}/%{name}-%{version}.tar.gz
BuildArch:      noarch

BuildRequires:  python-fedora
BuildRequires:  python-jinja2
Requires:       python-fedora
Requires:       python-jinja2

%description
This project helps new and existing contributors to Fedora find where
help is needed.

There are a number of project hosted on pagure.io which are participating
in this process by marking either Bugzilla tickets or Pagure issues as
'easyfix'.  fedora-gather-easyfix find them and gather them on a single
page.

A new contributor can consult this page and find a place/task they
would like to help with, contact the person in charge, and get started.

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
* Wed Jul 26 2017 Fedora Release Engineering <releng@fedoraproject.org> - 0.1.1-9
- Rebuilt for https://fedoraproject.org/wiki/Fedora_27_Mass_Rebuild

* Fri Feb 10 2017 Fedora Release Engineering <releng@fedoraproject.org> - 0.1.1-8
- Rebuilt for https://fedoraproject.org/wiki/Fedora_26_Mass_Rebuild

* Wed Feb 03 2016 Fedora Release Engineering <releng@fedoraproject.org> - 0.1.1-7
- Rebuilt for https://fedoraproject.org/wiki/Fedora_24_Mass_Rebuild

* Wed Jun 17 2015 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 0.1.1-6
- Rebuilt for https://fedoraproject.org/wiki/Fedora_23_Mass_Rebuild

* Sat Jun 07 2014 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 0.1.1-5
- Rebuilt for https://fedoraproject.org/wiki/Fedora_21_Mass_Rebuild

* Sat Aug 03 2013 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 0.1.1-4
- Rebuilt for https://fedoraproject.org/wiki/Fedora_20_Mass_Rebuild

* Wed Feb 13 2013 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 0.1.1-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_19_Mass_Rebuild

* Thu Jul 19 2012 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 0.1.1-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_18_Mass_Rebuild

* Mon Feb 27 2012 Pierre-Yves Chibon <pingou@pingoured.fr> - 0.1.1-1
- Update to 0.1.1
- Fix Source0 by adding the link to the fedorahosted release folder

* Mon Feb 20 2012 Pierre-Yves Chibon <pingou@pingoured.fr> - 0.1.0-1
- Initial packaging for Fedora
