from distutils.core import setup

setup(
    name='prometheus-enhanced-snmp-exporter',
    version='0.1dev',
    packages=['prometheus_enhanced_snmp_exporter'],
    scripts=['bin/prometheus-enhanced-snmp-exporter'],
    license='GPLv3',
    long_description=open('README.md').read(),
    install_requires=[
        "pyramid >= 1.5",
        "pysnmp >= 4.2",
        "APScheduler >= 3.5",
        "PyYAML >= 3.11"
    ]
)
