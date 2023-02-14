Summary: Sitepackage and other config files for Lmod
Name: Lmod-config
Version: 1.0
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

%build

%install
%{__mkdir_p} %{buildroot}%{_datadir}/lmod/lmod/libexec
%{__install} -p %{SOURCE0} %{buildroot}%{_datadir}/lmod/lmod/libexec

%{__mkdir_p} %{buildroot}%{_sysconfdir}/lmod
%{__install} -pm644 %{SOURCE1} %{buildroot}%{_sysconfdir}/lmod
%{__install} -pm644 %{SOURCE2} %{buildroot}%{_sysconfdir}/lmod
%{__install} -pm644 %{SOURCE3} %{buildroot}%{_sysconfdir}/lmod

%clean
rm -rf %{buildroot}

%files
%defattr(-,root,root,-)
%{_sysconfdir}/lmod/
%{_datadir}/lmod/lmod/libexec/run_lmod_cache.py

%changelog
* Tue Feb 14 2023 Ward Poelmans <ward.poelmans@vub.be>
- First version
