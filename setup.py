import os
from subprocess import check_output
from setuptools import setup
from setuptools.command.install import install

class InstallSystemdService(install):
    """
      Install as a systemd service and restart it
    """

    def run(self):
        install.run(self)
        current_dir_path = os.path.dirname(os.path.realpath(__file__))
        create_service_script_path = os.path.join(current_dir_path, 'create_service.sh')
        output = check_output(['/bin/bash', create_service_script_path])
        print(output)


setup(
    name='prometheus-enhanced-snmp-exporter',
    version='0.4alpha1',
    packages=['prometheus_enhanced_snmp_exporter'],
    scripts=['bin/prometheus-enhanced-snmp-exporter'],
    license='GPLv3',
    long_description=open('README.md').read(),
    classifiers=[
      'Development Status :: 3 - Alpha',
      'Environment :: Console',
      'Intended Audience :: Information Technology',
      'Intended Audience :: System Administrators',
      'Intended Audience :: Telecommunications Industry',
      'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
      'Operating System :: POSIX',
      'Topic :: System :: Monitoring',
      'Topic :: System :: Networking :: Monitoring',
      'Programming Language :: Python :: 3.5',
      'Programming Language :: Python :: 3.6',
      'Programming Language :: Python :: 3.7',
      'Programming Language :: Python :: 3.8'
    ],
    python_requires='>=3.5',
    install_requires=[
        "pyramid >= 1.5",
        "pysnmp >= 4.2",
        "APScheduler >= 3.5",
        "PyYAML >= 3.11",
        "influxdb >= 5.0.2"
    ],
    data_files=[
      ('/etc/prometheus-enhanced-snmp-exporter/', ['config/config.yaml']),
      ('/etc/default/', ['config/prometheus-enhanced-snmp-exporter']),
      ('/lib/systemd/system/', ['config/prometheus-enhanced-snmp-exporter@.service'])
    ],
    entry_points={
        'console_scripts': [
            'prometheus-enhanced-snmp-exporter = prometheus_enhanced_snmp_exporter:main'
        ]
    },
    cmdclass={'install': InstallSystemdService}
)

