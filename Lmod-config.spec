Summary: Sitepackage and other config files for Lmod
Name: Lmod-config
Version: 1.2
Release: 1
License: GPL
Group: Applications/System
BuildRoot: %{_tmppath}/%{name}-%{version}-%{release}-buildroot
BuildArch: noarch
Requires: Lmod
Source0: run_lmod_cache.py
Source1: SitePackage.lua
Source2: admin.list
Source3: lang.lua

%description
All the files we want for Lmod tweaking.

%prep

%build

%install
%{__mkdir_p} %{buildroot}%{_datadir}/lmod/lmod/libexec
%{__install} -p %{SOURCE0} %{buildroot}%{_datadir}/lmod/lmod/libexec

%{__mkdir_p} %{buildroot}%{_sysconfdir}/lmod
%{__install} -pm644 %{SOURCE1} %{buildroot}%{_sysconfdir}/lmod
%{__install} -pm644 %{SOURCE2} %{buildroot}%{_sysconfdir}/lmod
%{__install} -pm644 %{SOURCE3} %{buildroot}%{_sysconfdir}/lmod

# evil hack for CO7: avoid all postinstalls checks as it
# causes python3 issues.
%if 0%{?rhel} < 8
exit 0
%endif

%files
%defattr(-,root,root,-)
%{_sysconfdir}/lmod/
%{_datadir}/lmod/lmod/libexec/run_lmod_cache.py

%changelog
* Mon Feb 20 2023 Ward Poelmans <ward.poelmans@vub.be>
- Add special tweak for RHEL 7 building
* Wed Feb 15 2023 Samuel Moors <samuel.moors@vub.be>
- Add option in run_lmod_cache.py to show cache age
* Tue Feb 14 2023 Ward Poelmans <ward.poelmans@vub.be>
- First version
