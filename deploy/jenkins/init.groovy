import jenkins.model.Jenkins
import hudson.security.HudsonPrivateSecurityRealm
import hudson.security.FullControlOnceLoggedInAuthorizationStrategy
import hudson.model.ParametersDefinitionProperty
import hudson.model.BooleanParameterDefinition
import hudson.model.StringParameterDefinition
import hudson.model.ChoiceParameterDefinition
import org.jenkinsci.plugins.workflow.job.WorkflowJob
import org.jenkinsci.plugins.workflow.cps.CpsScmFlowDefinition
import hudson.plugins.git.GitSCM
import hudson.plugins.git.UserRemoteConfig
import hudson.plugins.git.BranchSpec
import jenkins.install.InstallState
import com.cloudbees.plugins.credentials.CredentialsScope
import com.cloudbees.plugins.credentials.SystemCredentialsProvider
import com.cloudbees.jenkins.plugins.sshcredentials.impl.BasicSSHUserPrivateKey
import org.jenkinsci.plugins.plaincredentials.impl.StringCredentialsImpl
import org.jenkinsci.plugins.plaincredentials.impl.FileCredentialsImpl
import com.cloudbees.plugins.credentials.SecretBytes
import hudson.util.Secret

// Initialize a fresh, dedicated localhost controller only. Do not reset it on restart.
def j = Jenkins.get()
def marker = new File(j.rootDir, '.devops-initialized')
if (marker.exists()) { return }
def secretDir = new File('/run/project-secrets')
def password = new File(secretDir, 'admin_password').text.trim()
if (password.length() < 16) { throw new IllegalStateException('Missing generated admin password') }
def realm = new HudsonPrivateSecurityRealm(false)
realm.createAccount('admin', password)
j.setSecurityRealm(realm)
def strategy = new FullControlOnceLoggedInAuthorizationStrategy()
strategy.setAllowAnonymousRead(false)
j.setAuthorizationStrategy(strategy)
j.setNumExecutors(1)
j.setLabelString('docker')
j.setSlaveAgentPort(-1)

def store = SystemCredentialsProvider.getInstance().getCredentials()
store.removeAll { it.id in ['sentinel-ec2-ssh', 'sentinel-grafana-password', 'sentinel-known-hosts'] }
store.add(new BasicSSHUserPrivateKey(CredentialsScope.GLOBAL, 'sentinel-ec2-ssh', 'ubuntu',
    new BasicSSHUserPrivateKey.DirectEntryPrivateKeySource(new File('/run/ec2_key').text), '',
    'Project EC2 deployment key'))
store.add(new StringCredentialsImpl(CredentialsScope.GLOBAL, 'sentinel-grafana-password',
    'Compose validation password', Secret.fromString(new File(secretDir, 'grafana_password').text.trim())))
store.add(new FileCredentialsImpl(CredentialsScope.GLOBAL, 'sentinel-known-hosts',
    'Known EC2 host key', 'known_hosts', SecretBytes.fromBytes(new File(secretDir, 'known_hosts').bytes)))
SystemCredentialsProvider.getInstance().save()

def job = j.getItem('Devops-project') ?: j.createProject(WorkflowJob, 'Devops-project')
def scm = new GitSCM(
    [new UserRemoteConfig('https://github.com/dishavpavoor/Devops-project.git', null, null, null)],
    [new BranchSpec('*/main')], false, [], null, null, []
)
job.setDefinition(new CpsScmFlowDefinition(scm, 'Jenkinsfile'))
job.addProperty(new ParametersDefinitionProperty(
    new BooleanParameterDefinition('DEPLOY', false, 'Deploy the tested image to EC2'),
    new StringParameterDefinition('DEPLOY_HOST', System.getenv('PROJECT_EC2_HOST') ?: '', 'EC2 IP or hostname'),
    new ChoiceParameterDefinition('TARGET_PLATFORM', ['linux/amd64', 'linux/arm64'] as String[], 'EC2 CPU architecture'),
    new BooleanParameterDefinition('SMALL_INSTANCE', true, 'Use bounded storage and memory for t3.micro')
))
job.save()
j.setInstallState(InstallState.INITIAL_SETUP_COMPLETED)
j.save()
marker.text = 'Dedicated project controller initialized.\n'
println('Devops-project controller and credentials initialized; no secret values logged.')
